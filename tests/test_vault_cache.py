"""Unit tests for navconfig.readers.vault_cache."""
import threading
import time

import pytest

from navconfig.readers import vault_cache
from navconfig.readers.vault_cache import (
    MISSING,
    CacheKey,
    VaultDocumentCache,
    get_document_cache,
    token_fingerprint,
)


def _key(path: str = "p") -> CacheKey:
    return CacheKey("http://v", token_fingerprint("t"), "m", 2, path)


class _Counter:
    def __init__(self, value=None):
        self.calls = 0
        self.value = {"a": 1} if value is None else value

    def __call__(self):
        self.calls += 1
        return self.value


def test_cache_hit_within_ttl():
    cache, loader = VaultDocumentCache(ttl=60), _Counter()
    assert cache.get_or_load(_key(), loader) == {"a": 1}
    assert cache.get_or_load(_key(), loader) == {"a": 1}
    assert loader.calls == 1


def test_cache_expires_after_ttl(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(vault_cache.time, "monotonic", lambda: now[0])
    cache, loader = VaultDocumentCache(ttl=10), _Counter()
    cache.get_or_load(_key(), loader)
    now[0] += 5
    cache.get_or_load(_key(), loader)
    assert loader.calls == 1
    now[0] += 6
    cache.get_or_load(_key(), loader)
    assert loader.calls == 2


def test_cache_ttl_zero_never_expires(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(vault_cache.time, "monotonic", lambda: now[0])
    cache, loader = VaultDocumentCache(ttl=0), _Counter()
    cache.get_or_load(_key(), loader)
    now[0] += 10**9
    cache.get_or_load(_key(), loader)
    assert loader.calls == 1


def test_cache_negative_entry():
    cache, loader = VaultDocumentCache(ttl=60), _Counter(MISSING)
    assert cache.get_or_load(_key(), loader) is MISSING
    assert cache.get_or_load(_key(), loader) is MISSING
    assert loader.calls == 1


def test_cache_exception_not_cached():
    cache = VaultDocumentCache(ttl=60)
    calls = []

    def loader():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return {"ok": True}

    with pytest.raises(RuntimeError):
        cache.get_or_load(_key(), loader)
    assert cache.get_or_load(_key(), loader) == {"ok": True}
    assert len(calls) == 2


def test_cache_single_flight_threads():
    cache = VaultDocumentCache(ttl=60)
    calls = []
    barrier = threading.Barrier(8)

    def loader():
        calls.append(1)
        time.sleep(0.05)
        return {"a": 1}

    results = []

    def worker():
        barrier.wait()
        results.append(cache.get_or_load(_key(), loader))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert results == [{"a": 1}] * 8


def test_cache_invalidate_predicate():
    cache, loader = VaultDocumentCache(ttl=60), _Counter()
    cache.get_or_load(_key("a"), loader)
    cache.get_or_load(_key("b"), loader)
    assert cache.invalidate(lambda k: k.path == "a") == 1
    cache.get_or_load(_key("b"), loader)
    assert loader.calls == 2
    cache.get_or_load(_key("a"), loader)
    assert loader.calls == 3
    assert cache.invalidate() == 2


def test_singleton_ttl_from_env(monkeypatch):
    monkeypatch.setenv("VAULT_CACHE_TTL", "12.5")
    vault_cache._reset_document_cache()
    assert get_document_cache().ttl == 12.5
    monkeypatch.setenv("VAULT_CACHE_TTL", "bad")
    vault_cache._reset_document_cache()
    assert get_document_cache().ttl == 300.0
    vault_cache._reset_document_cache()


def test_cache_put_during_load_not_overwritten():
    cache = VaultDocumentCache(ttl=60)

    def loader():
        cache.put(_key(), {"fresh": True})  # write-through while loading
        return {"stale": True}

    assert cache.get_or_load(_key(), loader) == {"stale": True}
    assert cache.get_or_load(_key(), lambda: {"never": 1}) == {"fresh": True}


def test_cache_invalidate_during_load_drops_stale():
    cache = VaultDocumentCache(ttl=60)

    def loader():
        cache.invalidate()
        return {"stale": True}

    cache.get_or_load(_key(), loader)
    assert cache.get_or_load(_key(), lambda: {"new": 1}) == {"new": 1}
