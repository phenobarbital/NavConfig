"""Process-wide cache of HashiCorp Vault KV documents."""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Final

MISSING: Final = object()
"""Negative-cache marker: the Vault path does not exist (InvalidPath)."""


def token_fingerprint(token: str) -> str:
    """Return sha256(token) hex digest truncated to 16 chars.

    Args:
        token: Raw Vault token.

    Returns:
        First 16 hex characters of the sha256 digest.
    """
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CacheKey:
    """Identity of a cached KV document.

    Attributes:
        url: Vault URL.
        token_fp: Token fingerprint (never the raw token).
        mount: KV mount point.
        version: KV engine version (1 or 2).
        path: Secret path under the mount.
    """
    url: str
    token_fp: str
    mount: str
    version: int
    path: str


@dataclass
class CacheEntry:
    """Cached KV document (dict) or MISSING, with its fetch time.

    Attributes:
        data: The KV document, or MISSING.
        fetched_at: ``time.monotonic()`` at fetch time.
    """
    data: dict | object
    fetched_at: float


class VaultDocumentCache:
    """Thread-safe TTL cache with negative entries and single-flight loading."""

    def __init__(self, ttl: float = 300.0) -> None:
        """Create the cache.

        Args:
            ttl: Seconds before an entry expires; ``<= 0`` means never.
        """
        self._ttl = float(ttl)
        self._entries: dict[CacheKey, CacheEntry] = {}
        # per-key [lock, refcount]; removed once nobody holds or awaits it
        self._key_locks: dict[CacheKey, list] = {}
        self._lock = threading.Lock()
        # per-key generation: bumped by put/invalidate to fence stale loads
        self._gens: dict[CacheKey, int] = {}

    @property
    def ttl(self) -> float:
        """Configured TTL in seconds (``<= 0`` means entries never expire)."""
        return self._ttl

    def _is_fresh(self, entry: CacheEntry) -> bool:
        if self._ttl <= 0:
            return True
        return (time.monotonic() - entry.fetched_at) < self._ttl

    def _acquire(self, key: CacheKey) -> threading.Lock:
        """Acquire the per-key lock (refcounted so it can be pruned safely)."""
        with self._lock:
            slot = self._key_locks.get(key)
            if slot is None:
                slot = self._key_locks[key] = [threading.Lock(), 0]
            slot[1] += 1
        slot[0].acquire()
        return slot[0]

    def _release(self, key: CacheKey, lock: threading.Lock) -> None:
        lock.release()
        with self._lock:
            slot = self._key_locks.get(key)
            if slot is not None:
                slot[1] -= 1
                if slot[1] <= 0:
                    del self._key_locks[key]
                    if key not in self._entries:
                        self._gens.pop(key, None)

    @contextmanager
    def locked(self, key: CacheKey) -> Iterator[None]:
        """Hold the single-flight lock of ``key`` (for read-modify-write).

        Writers use this so a set()/delete() and its ``put`` are atomic with
        respect to loaders and other writers of the same document.

        Args:
            key: Cache key whose lock to hold.
        """
        lock = self._acquire(key)
        try:
            yield
        finally:
            self._release(key, lock)

    def get_or_load(
        self, key: CacheKey, loader: Callable[[], dict | object]
    ) -> dict | object:
        """Return a fresh cached value or load it single-flight.

        Args:
            key: Cache key.
            loader: Callable returning a dict, or MISSING. Exceptions
                propagate and are not cached.

        Returns:
            The document dict, or MISSING.
        """
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None and self._is_fresh(entry):
                return entry.data
        with self.locked(key):
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and self._is_fresh(entry):
                    return entry.data
                gen = self._gens.get(key, 0)
            data = loader()  # outside the global lock
            with self._lock:
                # a put()/invalidate() of THIS key during the load makes the
                # result stale; other keys' activity is irrelevant
                if self._gens.get(key, 0) == gen:
                    self._entries[key] = CacheEntry(data, time.monotonic())
            return data

    def put(self, key: CacheKey, data: dict | object) -> None:
        """Store or replace an entry (write-through).

        Args:
            key: Cache key.
            data: Document dict or MISSING.
        """
        with self._lock:
            self._gens[key] = self._gens.get(key, 0) + 1
            self._entries[key] = CacheEntry(data, time.monotonic())

    def invalidate(
        self, predicate: Callable[[CacheKey], bool] | None = None
    ) -> int:
        """Drop matching entries and fence in-flight loads of matching keys.

        Args:
            predicate: Selects keys to drop; all when None.

        Returns:
            Number of cached entries dropped.
        """
        with self._lock:
            candidates = set(self._entries) | set(self._key_locks)
            if predicate is not None:
                candidates = {k for k in candidates if predicate(k)}
            dropped = 0
            for k in candidates:
                self._gens[k] = self._gens.get(k, 0) + 1
                if self._entries.pop(k, None) is not None:
                    dropped += 1
            return dropped


_cache: VaultDocumentCache | None = None
_cache_lock = threading.Lock()


def get_document_cache() -> VaultDocumentCache:
    """Return the module singleton; TTL read once from VAULT_CACHE_TTL.

    A value ``<= 0`` disables expiry; an unparsable value logs a warning
    and falls back to 300 seconds.

    Returns:
        The process-wide VaultDocumentCache.
    """
    global _cache  # pylint: disable=W0603
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                raw = os.getenv("VAULT_CACHE_TTL", "300")
                try:
                    ttl = float(raw)
                except ValueError:
                    logging.getLogger(__name__).warning(
                        "Invalid VAULT_CACHE_TTL=%r; using 300 seconds", raw
                    )
                    ttl = 300.0
                _cache = VaultDocumentCache(ttl=ttl)
    return _cache


def _reset_document_cache() -> None:
    """Testing helper: drop the singleton so the next call re-reads the env."""
    global _cache  # pylint: disable=W0603
    with _cache_lock:
        _cache = None
