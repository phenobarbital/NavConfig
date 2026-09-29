"""Process-wide cache of HashiCorp Vault KV documents."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable
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
        self._key_locks: dict[CacheKey, threading.Lock] = {}
        self._lock = threading.Lock()
        self._generation = 0  # bumped by put/invalidate; fences stale loads

    @property
    def ttl(self) -> float:
        """Configured TTL in seconds."""
        return self._ttl

    def _is_fresh(self, entry: CacheEntry) -> bool:
        if self._ttl <= 0:
            return True
        return (time.monotonic() - entry.fetched_at) < self._ttl

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
            key_lock = self._key_locks.get(key)
            if key_lock is None:
                key_lock = self._key_locks[key] = threading.Lock()
        with key_lock:
            with self._lock:
                entry = self._entries.get(key)
                if entry is not None and self._is_fresh(entry):
                    return entry.data
            with self._lock:
                gen = self._generation
            data = loader()  # outside the global lock
            with self._lock:
                # a put()/invalidate() during the load makes this result stale
                if self._generation == gen:
                    self._entries[key] = CacheEntry(data, time.monotonic())
            return data

    def put(self, key: CacheKey, data: dict | object) -> None:
        """Store or replace an entry (write-through).

        Args:
            key: Cache key.
            data: Document dict or MISSING.
        """
        with self._lock:
            self._generation += 1
            self._entries[key] = CacheEntry(data, time.monotonic())

    def invalidate(
        self, predicate: Callable[[CacheKey], bool] | None = None
    ) -> int:
        """Drop matching entries.

        Args:
            predicate: Selects keys to drop; all when None.

        Returns:
            Number of entries dropped.
        """
        with self._lock:
            if predicate is None:
                doomed = list(self._entries)
            else:
                doomed = [k for k in self._entries if predicate(k)]
            self._generation += 1
            for k in doomed:
                del self._entries[k]  # per-key locks are kept: they may be held
            return len(doomed)


_cache: VaultDocumentCache | None = None
_cache_lock = threading.Lock()


def get_document_cache() -> VaultDocumentCache:
    """Return the module singleton; TTL read once from VAULT_CACHE_TTL.

    Returns:
        The process-wide VaultDocumentCache.
    """
    global _cache  # pylint: disable=W0603
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                try:
                    ttl = float(os.getenv("VAULT_CACHE_TTL", "300"))
                except ValueError:
                    ttl = 300.0
                _cache = VaultDocumentCache(ttl=ttl)
    return _cache


def _reset_document_cache() -> None:
    """Testing helper: drop the singleton so the next call re-reads the env."""
    global _cache  # pylint: disable=W0603
    with _cache_lock:
        _cache = None
