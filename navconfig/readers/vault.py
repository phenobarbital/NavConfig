import asyncio
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
        self._url = url
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
        return dict(value) if isinstance(value, dict) else value

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
            logging.debug(f"Vault get error for {key}: {e}")
            return default
        if data is MISSING:
            return default
        if secret_key == "*":
            return dict(data)
        secret_data = data.get(secret_key, default)
        if sub_key is not None:
            return secret_data.get(sub_key, default)
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
            logging.debug(f"Vault exists error for {key}: {e}")
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
        try:
            current = self._fetch_document(secret_path)
            doc = {} if current is MISSING else dict(current)
            doc[secret_key] = value
            self._write_document(secret_path, doc)
        except Exception as ex:
            raise ValueError(
                f"Error writing to Vault: {ex}"
            )
        self._cache.put(self._cache_key(secret_path), doc)

    def delete(self, key: str, secret_path: str = None) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()
        secret_path, secret_key = self._split_key(key)
        try:
            current = self._fetch_document(secret_path)
            if current is MISSING:
                raise KeyError(f"path '{secret_path}' does not exist")
            doc = dict(current)
            if secret_key in doc:
                del doc[secret_key]
                self._write_document(secret_path, doc)
                self._cache.put(self._cache_key(secret_path), doc)
            return True
        except Exception as e:  # pylint: disable=W0703
            logging.warning(
                f"Error deleting key '{key}' from '{secret_path}': {e}"
            )
            return False

    def list(self, path: str = None, filter: str = None) -> dict:
        """
        List and return all secrets from the specified path.

        Returns the actual secret data (key-value pairs), as a shallow
        copy of the cached document, so it is compatible with the unified
        vault loader and callers can't mutate the cache.
        """
        if self.enabled is False:
            raise ReaderNotSet()

        secret_path = path or self._env

        try:
            data = self._read_document(secret_path)
            if data is MISSING:
                logging.debug(f"No secrets found at vault path '{secret_path}'")
                return {}
            if filter:
                data = {
                    k: v for k, v in data.items()
                    if k.startswith(filter)
                }
            else:
                data = dict(data)
            logging.debug(f"Retrieved {len(data)} secrets from vault path '{secret_path}'")
            return data
        except Exception as e:  # pylint: disable=W0703
            logging.warning(f"Error listing secrets at path '{secret_path}': {e}")
            return {}

    def invalidate(self, path: str | None = None) -> None:
        """Drop this reader's cached documents (one path, or all)."""
        mine = (self._url, self._token_fp, self._mount, self.version)

        def _match(k: CacheKey) -> bool:
            if (k.url, k.token_fp, k.mount, k.version) != mine:
                return False
            return path is None or k.path == path

        self._cache.invalidate(_match)

    def refresh(self, path: str | None = None) -> dict:
        """Invalidate ``path`` (default: env path) and re-read it."""
        target = path or self._env
        self.invalidate(target)
        return self.list(target)

    async def aget(
        self,
        key: str,
        default: Any = None,
        sub_key: str | None = None,
    ) -> Any:
        """Async wrapper over :meth:`get` (runs in a worker thread)."""
        return await asyncio.to_thread(self.get, key, default, "secrets", sub_key)

    async def aexists(self, key: str) -> bool:
        """Async wrapper over :meth:`exists`."""
        return await asyncio.to_thread(self.exists, key)

    async def alist(
        self, path: str | None = None, filter: str | None = None
    ) -> dict:
        """Async wrapper over :meth:`list`."""
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
        for p, res in zip(targets, results):
            if isinstance(res, BaseException):
                logging.warning(f"Vault prefetch failed for '{p}': {res}")
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
