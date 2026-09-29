# TASK-001: VaultDocumentCache module (TTL, negative entries, single-flight)

**Feature**: FEAT-001 — Vault Document Cache & Async Vault Read
**Spec**: `sdd/specs/async-vault-read.spec.md`
**Status**: pending
**Priority**: high
**Estimated effort**: M (2-4h)
**Depends-on**: none
**Assigned-to**: unassigned

---

## Context

Implements spec §3 **Module 1**. This is the storage layer for the whole feature:
a process-wide, thread-safe cache of whole Vault KV documents. `VaultReader`
(TASK-002) routes every read through it, which gives the spec's goals:
G1 (one read per path per TTL, shared across instances), G3 (TTL), G4 (negative
caching, but no caching of transient errors) and G6 (single-flight).

---

## Scope

- Create `navconfig/readers/vault_cache.py`, containing:
  - the `MISSING` sentinel;
  - `token_fingerprint()`;
  - the `CacheKey` and `CacheEntry` dataclasses;
  - `VaultDocumentCache` with `ttl`, `get_or_load`, `put` and `invalidate`;
  - the `get_document_cache()` module singleton, plus a private reset helper for tests.
- The TTL is read **once** from `VAULT_CACHE_TTL` (float seconds, default `300`). `<= 0` means entries never expire.
- Single-flight: a per-key `threading.Lock`. **Never** hold the global lock while calling the loader.
- Exceptions raised by the loader propagate and are **not** cached.
- Write `tests/test_vault_cache.py` covering the 7 M1 tests in spec §4.

**NOT in scope**: any change to `VaultReader` (TASK-002), to Kardex (TASK-003), or to docs and the CHANGELOG (TASK-004).

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `navconfig/readers/vault_cache.py` | CREATE | Cache module |
| `tests/test_vault_cache.py` | CREATE | Unit tests for M1 |

---

## Codebase Contract (Anti-Hallucination)

### Verified Imports
```python
# stdlib only. No third-party imports in this module.
import hashlib, os, threading, time
from dataclasses import dataclass
from typing import Callable, Dict, Final, Optional, Union
```

### Existing Signatures to Use
None. This is a new, self-contained module.

### Does NOT Exist
- ~~`pydantic`~~: not a navconfig dependency. Use `dataclasses`.
- ~~`navconfig.readers.vault_cache`~~: doesn't exist yet. This task creates it.
- ~~`cachetools`~~: not a dependency. Don't add one.

---

## Complexity Contract

```json
{
  "schema_version": 1,
  "targets": [
    {"path": "navconfig/readers/vault_cache.py", "action": "CREATE"},
    {"path": "tests/test_vault_cache.py", "action": "CREATE"}
  ],
  "contract_symbols": []
}
```

---

## Implementation Notes

### Key Constraints
- Stdlib only, with Google-style docstrings and type hints.
- Use `time.monotonic()` for timestamps, so tests can monkeypatch `navconfig.readers.vault_cache.time.monotonic`.
- The raw token never appears in `CacheKey` or in logs. Only `token_fingerprint()` output (the first 16 hex chars of the sha256) does.
- `pyproject.toml` sets `filterwarnings = ["error", ...]`, so the tests must not emit warnings.

### Locking design (decided)
- `self._lock` (global) guards `self._entries: Dict[CacheKey, CacheEntry]` and `self._key_locks: Dict[CacheKey, threading.Lock]`.
- `get_or_load` works in these steps:
  1. Under the global lock, return the value if the entry is fresh. Otherwise get or create the per-key lock.
  2. Acquire the per-key lock.
  3. Re-check freshness under the global lock (another thread may have filled it).
  4. Call `loader()` **outside** the global lock.
  5. Store the entry under the global lock and return.

---

## Implementation Blueprint

### `navconfig/readers/vault_cache.py` (CREATE)
```python
"""Process-wide cache of HashiCorp Vault KV documents."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Final, Optional, Union

MISSING: Final = object()
"""Negative-cache marker: the Vault path does not exist (InvalidPath)."""


def token_fingerprint(token: str) -> str:
    """Return sha256(token) hex digest truncated to 16 chars."""
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class CacheKey:
    """Identity of a cached KV document."""
    url: str
    token_fp: str
    mount: str
    version: int
    path: str


@dataclass
class CacheEntry:
    """Cached KV document (dict) or MISSING, with its fetch time."""
    data: Union[dict, object]
    fetched_at: float


class VaultDocumentCache:
    """Thread-safe TTL cache with negative entries and single-flight loading."""

    def __init__(self, ttl: float = 300.0) -> None:
        # FILL IN: store ttl, _entries, _key_locks, _lock (threading.Lock)
        raise NotImplementedError

    @property
    def ttl(self) -> float:
        # FILL IN
        raise NotImplementedError

    def _is_fresh(self, entry: CacheEntry) -> bool:
        # FILL IN: ttl <= 0 -> True; else monotonic() - fetched_at < ttl
        raise NotImplementedError

    def get_or_load(
        self, key: CacheKey, loader: Callable[[], Union[dict, object]]
    ) -> Union[dict, object]:
        # FILL IN: locking design above; loader exceptions propagate, not cached
        raise NotImplementedError

    def put(self, key: CacheKey, data: Union[dict, object]) -> None:
        # FILL IN
        raise NotImplementedError

    def invalidate(
        self, predicate: Optional[Callable[[CacheKey], bool]] = None
    ) -> int:
        # FILL IN: drop all (predicate None) or matching; return count
        raise NotImplementedError


_cache: Optional[VaultDocumentCache] = None
_cache_lock = threading.Lock()


def get_document_cache() -> VaultDocumentCache:
    """Return the module singleton; TTL read once from VAULT_CACHE_TTL."""
    # FILL IN: double-checked init; invalid VAULT_CACHE_TTL -> 300.0
    raise NotImplementedError


def _reset_document_cache() -> None:
    """Testing helper: drop the singleton so the next call re-reads the env."""
    # FILL IN
    raise NotImplementedError
```
**Why this shape**: it follows spec §2 (Data Models) and §3 M1 exactly. Keeping the cache in its own module lets `VaultReader` and the tests share the singleton without import cycles.

### FILL IN checklist
- [ ] `VaultDocumentCache.get_or_load`: single-flight without holding the global lock during I/O
- [ ] `get_document_cache`: parses `VAULT_CACHE_TTL` as float, falling back to 300 on bad input
- [ ] `invalidate`: also prunes the `_key_locks` entries that were dropped

---

## Acceptance Criteria

- [ ] `pytest tests/test_vault_cache.py -v` passes (7 tests).
- [ ] `from navconfig.readers.vault_cache import VaultDocumentCache, get_document_cache, MISSING, CacheKey, token_fingerprint` works.
- [ ] `test_cache_single_flight_threads`: the loader is called exactly once with 8+ threads.
- [ ] The full `pytest` suite still passes.

---

## Validation Commands

- `pytest tests/test_vault_cache.py -q`

---

## Test Specification

```python
# tests/test_vault_cache.py
import threading
import pytest
from navconfig.readers import vault_cache as vc
from navconfig.readers.vault_cache import CacheKey, MISSING, VaultDocumentCache

KEY = CacheKey("http://v", "fp", "navigator", 2, "dev")

def test_cache_hit_within_ttl(): ...           # loader called once for 2 gets
def test_cache_expires_after_ttl(monkeypatch): ...  # patch vc.time.monotonic
def test_cache_ttl_zero_never_expires(monkeypatch): ...
def test_cache_negative_entry(): ...           # loader returns MISSING once
def test_cache_exception_not_cached(): ...     # raises, then succeeds on retry
def test_cache_single_flight_threads(): ...    # threading.Barrier + slow loader
def test_cache_invalidate_predicate(): ...     # drop only path == "a"
```

---

## Agent Instructions

1. Work in the feature worktree `.claude/worktrees/feat-FEAT-001-async-vault-read`, never on `new-release`.
2. Read the spec for full context.
3. Set this task to `"in-progress"` in `sdd/tasks/.index.json`.
4. Implement from the blueprint, run the validation commands and the full `pytest`, and commit only the listed files.
5. Move this file to `sdd/tasks/completed/`, set its index status to `"done"`, and fill in the Completion Note.

---

## Completion Note

*(Agent fills this in when done)*

**Completed by**:
**Date**:
**Notes**:

**Deviations from spec**:
