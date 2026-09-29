import asyncio
import copy
import logging
import os
from collections.abc import Iterable
from typing import Any

import hvac
import urllib3

from ..exceptions import ReaderNotSet
from .abstract import AbstractReader
from .vault_cache import MISSING, CacheKey, get_document_cache, token_fingerprint

# Disable warnings for insecure requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

class VaultReader(AbstractReader):
    """VaultReader.

    Description: Class for HashiCorp Vault Reader.

    The secret path segment under the mount point is resolved as:
    ``VAULT_ENV`` (if set and non-empty) > ``env`` argument > ``ENV``.
    This allows pointing to a custom vault environment without
    changing the ``ENV`` used by the rest of the application.
    """

    def __init__(self, env: str = None) -> None:
        url = os.getenv(
            "VAULT_URL",
            "http://localhost:8200"
        )
        token = os.getenv("VAULT_TOKEN")
        self.version = int(os.getenv("VAULT_VERSION", 2))
        self._mount = os.getenv("VAULT_MOUNT_POINT", "navigator")
        self._env = os.getenv("VAULT_ENV") or env or os.getenv("ENV", "")
        # normalized so readers differing only by a trailing slash share cache
        self._url = url.rstrip("/")
        self._token_fp = token_fingerprint(token or "")
        self._cache = get_document_cache()
        if not token:
            raise ValueError("VAULT_TOKEN is not set")
        try:
            self.client = hvac.Client(url=url, token=token)
            self.open()
        except Exception as err:  # pylint: disable=W0703
            self.enabled = False
            raise ReaderNotSet(f"Vault Error: {err}") from err
        self.enabled = True

    def open(self) -> bool:
        if self.client.is_authenticated():
            logging.debug("Hashicorp Vault Connected")
            return True
        return False

    def close(self) -> None:
        pass

    def _split_key(self, key: str) -> tuple[str, str]:
        """Split 'a/b/KEY' on the LAST '/'; bare keys resolve to self._env.

        Args:
            key: Secret key, optionally prefixed by a path.

        Returns:
            Tuple of (secret_path, secret_key).
        """
        path, sep, name = key.rpartition("/")
        if not sep or not path:
            return self._env, name if sep else key
        return path, name

    def _cache_key(self, path: str) -> CacheKey:
        """Build the shared-cache key for ``path`` on this reader's Vault."""
        return CacheKey(self._url, self._token_fp, self._mount, self.version, path)

    def _fetch_document(self, path: str) -> dict | object:
        """Perform ONE hvac read of the KV document at ``path``.

        Returns:
            The document dict, or MISSING when the path does not exist.

        Raises:
            ValueError: Unsupported KV version.
            Exception: Any transient hvac error (never cached).
        """
        try:
            if self.version == 1:
                response = self.client.secrets.kv.v1.read_secret(
                    path=path, mount_point=self._mount
                )
                return response["data"]
            if self.version == 2:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=path, mount_point=self._mount
                )
                return response["data"]["data"]
        except hvac.exceptions.InvalidPath:
            return MISSING
        raise ValueError("Invalid KV version specified")

    def _read_document(self, path: str) -> dict | object:
        """Read a document through the shared cache."""
        return self._cache.get_or_load(
            self._cache_key(path), lambda: self._fetch_document(path)
        )

    def _write_document(self, path: str, doc: dict) -> None:
        """Write a whole document to Vault (kv v1/v2)."""
        if self.version == 1:
            self.client.secrets.kv.v1.create_or_update_secret(
                path=path, secret=doc, mount_point=self._mount
            )
        elif self.version == 2:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path, secret=doc, mount_point=self._mount
            )

    @staticmethod
    def _copy(value: Any) -> Any:
        """Deep-copy a value read from the cache so callers can't mutate it."""
        return copy.deepcopy(value)

    def get(
        self,
        key: str,
        default: Any = None,
        path: str = "secrets",
        sub_key: str = None,
    ) -> Any:
        if self.enabled is False:
            raise ReaderNotSet()
        secret_path, secret_key = self._split_key(key)
        try:
            data = self._read_document(secret_path)
        except Exception as e:  # pylint: disable=W0703
            logger.debug("Vault get error for %s: %s", key, e)
            return default
        if data is MISSING:
            return default
        if secret_key == "*":
            return self._copy(data)
        secret_data = data.get(secret_key, default)
        if sub_key is not None:
            if not isinstance(secret_data, dict):
                return default
            return self._copy(secret_data.get(sub_key, default))
        return self._copy(secret_data)

    def exists(
        self,
        key: str,
    ) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()
        secret_path, secret_key = self._split_key(key)
        try:
            data = self._read_document(secret_path)
        except Exception as e:  # pylint: disable=W0703
            logger.debug("Vault exists error for %s: %s", key, e)
            return False
        if data is MISSING:
            return False
        if secret_key == "*":
            return True
        return secret_key in data

    def set(
        self,
        key: str,
        value: Any,
        **kwargs
    ) -> None:
        if self.enabled is False:
            raise ReaderNotSet()
        secret_path, secret_key = self._split_key(key)
        ckey = self._cache_key(secret_path)
        # the per-key lock makes read-modify-write-put atomic against other
        # writers and loaders of the same document (cache never diverges)
        with self._cache.locked(ckey):
            try:
                current = self._fetch_document(secret_path)
                doc = {} if current is MISSING else copy.deepcopy(current)
                doc[secret_key] = value
                self._write_document(secret_path, doc)
            except Exception as ex:
                raise ValueError(
                    f"Error writing to Vault: {ex}"
                ) from ex
            self._cache.put(ckey, doc)

    def delete(self, key: str, secret_path: str = None) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()
        if secret_path:
            # explicit path wins; the key is then the bare secret name
            _, secret_key = self._split_key(key)
        else:
            secret_path, secret_key = self._split_key(key)
        ckey = self._cache_key(secret_path)
        try:
            with self._cache.locked(ckey):
                current = self._fetch_document(secret_path)
                if current is MISSING:
                    raise KeyError(f"path '{secret_path}' does not exist")
                doc = copy.deepcopy(current)
                if secret_key in doc:
                    del doc[secret_key]
                    self._write_document(secret_path, doc)
                    self._cache.put(ckey, doc)
            return True
        except Exception as e:  # pylint: disable=W0703
            logger.warning(
                "Error deleting key '%s' from '%s': %s", key, secret_path, e
            )
            return False

    def list(self, path: str = None, filter: str = None) -> dict:
        """List and return all secrets from the specified path.

        Args:
            path: Secret path (defaults to the reader's env path).
            filter: Only keys starting with this prefix are returned.

        Returns:
            A deep copy of the cached document (so callers can't mutate the
            cache), or ``{}`` when the path is missing or on error.
        """
        if self.enabled is False:
            raise ReaderNotSet()

        secret_path = path or self._env

        try:
            data = self._read_document(secret_path)
            if data is MISSING:
                logger.debug("No secrets found at vault path '%s'", secret_path)
                return {}
            if filter:
                data = {
                    k: self._copy(v) for k, v in data.items()
                    if k.startswith(filter)
                }
            else:
                data = self._copy(data)
            logger.debug(
                "Retrieved %d secrets from vault path '%s'", len(data), secret_path
            )
            return data
        except Exception as e:  # pylint: disable=W0703
            logger.warning("Error listing secrets at path '%s': %s", secret_path, e)
            return {}

    def invalidate(self, path: str | None = None) -> None:
        """Drop this reader's cached documents.

        Args:
            path: Only this path; all of this reader's paths when None.
        """
        mine = (self._url, self._token_fp, self._mount, self.version)

        def _match(k: CacheKey) -> bool:
            if (k.url, k.token_fp, k.mount, k.version) != mine:
                return False
            return path is None or k.path == path

        self._cache.invalidate(_match)

    def refresh(self, path: str | None = None) -> dict:
        """Invalidate ``path`` and re-read it from Vault.

        Args:
            path: Path to refresh (defaults to the reader's env path).

        Returns:
            The freshly read document (``{}`` if missing).
        """
        target = path or self._env
        self.invalidate(target)
        return self.list(target)

    async def aget(
        self,
        key: str,
        default: Any = None,
        sub_key: str | None = None,
    ) -> Any:
        """Async wrapper over :meth:`get` (runs in a worker thread).

        Args:
            key: Secret key, optionally prefixed by a path.
            default: Value returned when the key is missing or on error.
            sub_key: Optional key inside a dict-valued secret.

        Returns:
            The secret value, or ``default``.
        """
        return await asyncio.to_thread(self.get, key, default, "secrets", sub_key)

    async def aexists(self, key: str) -> bool:
        """Async wrapper over :meth:`exists`.

        Args:
            key: Secret key, optionally prefixed by a path.

        Returns:
            True when the key exists in Vault.
        """
        return await asyncio.to_thread(self.exists, key)

    async def alist(
        self, path: str | None = None, filter: str | None = None
    ) -> dict:
        """Async wrapper over :meth:`list`.

        Args:
            path: Secret path (defaults to the reader's env path).
            filter: Only keys starting with this prefix are returned.

        Returns:
            The document copy, as :meth:`list`.
        """
        return await asyncio.to_thread(self.list, path, filter)

    async def aload(
        self, paths: Iterable[str] | None = None
    ) -> dict[str, bool]:
        """Prefetch documents concurrently into the shared cache.

        Args:
            paths: Paths to prefetch; defaults to ``[self._env]``.

        Returns:
            Mapping of path -> found. Failures log a warning and map to False.
        """
        if self.enabled is False:
            raise ReaderNotSet()
        targets = list(paths) if paths is not None else [self._env]
        results = await asyncio.gather(
            *(asyncio.to_thread(self._read_document, p) for p in targets),
            return_exceptions=True,
        )
        out: dict[str, bool] = {}
        for p, res in zip(targets, results, strict=True):
            if isinstance(res, Exception):
                logger.warning("Vault prefetch failed for '%s': %s", p, res)
                out[p] = False
            else:
                out[p] = isinstance(res, dict)
        return out

    def list_paths(self, path: str = None) -> list:
        """
        List secret paths (directories/keys) at the specified path.

        This is separate from list() which returns actual secret data.
        Useful for discovering what secret paths are available.
        """
        if self.enabled is False:
            raise ReaderNotSet()

        secret_path = path or ""

        try:
            if self.version == 1:
                # KV v1 doesn't have a list operation, return empty list
                logging.debug("KV v1 doesn't support path listing")
                return []

            elif self.version == 2:
                # For KV v2, use list_secrets to get paths
                response = self.client.secrets.kv.v2.list_secrets(
                    path=secret_path, mount_point=self._mount
                )
                return response["data"]["keys"]

        except hvac.exceptions.InvalidPath:
            logging.debug(f"No paths found at '{secret_path}'")
            return []
        except Exception as e:
            logging.debug(f"Error listing paths at '{secret_path}': {e}")
            return []
