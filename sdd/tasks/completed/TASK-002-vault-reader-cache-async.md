# TASK-002: VaultReader refactor (cache-through reads, write-through, async API)

**Feature**: FEAT-001 — Vault Document Cache & Async Vault Read
**Spec**: `sdd/specs/async-vault-read.spec.md`
**Status**: pending
**Priority**: high
**Estimated effort**: L (4-8h)
**Depends-on**: TASK-001
**Assigned-to**: unassigned

---

## Context

Implements spec §3 **Module 2**. Today `VaultReader.get`, `exists`, `list`, `set` and
`delete` each call hvac directly and duplicate the KV v1/v2 read logic. This task
gives the reader a single fetch point (`_fetch_document`), a cache-through read
(`_read_document`) and unified key parsing (`_split_key`, which splits on the last `/`).
It also adds async wrappers (`asyncio.to_thread`) and prefetching (`aload`).

---

## Scope

- In `__init__`, store `self._url`, `self._token_fp` (via `token_fingerprint`) and `self._cache = get_document_cache()`. Construction behavior is otherwise unchanged.
- Add these private helpers:
  - `_split_key(key)`: splits on the last `/`.
  - `_cache_key(path)`.
  - `_fetch_document(path)`: one hvac read, v1 or v2. Returns `MISSING` on `hvac.exceptions.InvalidPath`; other exceptions propagate.
  - `_read_document(path)`.
- Rewrite `get`, `exists` and `list` on top of `_read_document`, keeping their current signatures and error contracts:
  - `get` returns `default` on any error or missing path. It keeps the `"*"` and `sub_key` behavior.
  - `exists` returns `False` on error or a missing path, and `True` for `"*"` when the doc exists.
  - `list` returns `{}` on error or a missing path, and otherwise a **shallow copy**, filtered if `filter` is given.
  - `get` of a dict-valued secret (and `"*"`) returns a shallow copy, so callers can't mutate the cache.
- Rewrite `set` and `delete` to use `_split_key`, so they split on the last `/` like `get` does. Each reads the current doc fresh through `_fetch_document` (bypassing the cache), writes it back, then calls `self._cache.put(key, new_doc)`.
  - `set` keeps its `ValueError("Error writing to Vault: ...")` contract.
  - `delete` keeps returning a bool.
- Add `invalidate(path=None)` and `refresh(path=None)`.
- Add `aget`, `aexists`, `alist` (each `asyncio.to_thread` over the sync method) and `aload(paths=None)`.
- Write `tests/test_vault_reader.py` covering the 10 M2 tests in spec §4, using a `fake_hvac` fixture.

**NOT in scope**: `list_paths` (leave it untouched), Kardex changes (TASK-003), docs and the CHANGELOG (TASK-004), and `AbstractReader` (must stay unchanged).

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `navconfig/readers/vault.py` | MODIFY | Cache-through reader + async API |
| `tests/test_vault_reader.py` | CREATE | Unit tests for M2 |

---

## Codebase Contract (Anti-Hallucination)

### Verified Imports
```python
import hvac                                           # navconfig/readers/vault.py:4
from ..exceptions import ReaderNotSet                 # navconfig/readers/vault.py:5
from .abstract import AbstractReader                  # navconfig/readers/vault.py:6
from .vault_cache import (                            # created by TASK-001
    MISSING, CacheKey, get_document_cache, token_fingerprint,
)
```

### Existing Signatures to Use
```python
# navconfig/readers/vault.py
class VaultReader(AbstractReader):                                      # line 14
    def __init__(self, env: str = None) -> None                         # line 25; locals url, token
    #   self.version (int, VAULT_VERSION default 2)                     # line 31
    #   self._mount  (VAULT_MOUNT_POINT default "navigator")            # line 32
    #   self._env    (VAULT_ENV > env > ENV)                            # line 33
    #   self.client = hvac.Client(url=url, token=token); self.open()    # lines 37-38
    def get(self, key, default=None, path="secrets", sub_key=None) -> Any   # line 53
    def exists(self, key: str) -> bool                                  # line 97
    def set(self, key: str, value: Any, **kwargs) -> None               # line 134 (splits on FIRST '/')
    def delete(self, key: str, secret_path: str = None) -> bool         # line 198 (splits on FIRST '/')
    def list(self, path: str = None, filter: str = None) -> dict        # line 242
    def list_paths(self, path: str = None) -> list                      # line 289 (DO NOT TOUCH)

# hvac calls in use today:
client.secrets.kv.v1.read_secret(path=..., mount_point=...)["data"]
client.secrets.kv.v2.read_secret_version(path=..., mount_point=...)["data"]["data"]
client.secrets.kv.v1.create_or_update_secret(path=..., secret=..., mount_point=...)
client.secrets.kv.v2.create_or_update_secret(path=..., secret=..., mount_point=...)
hvac.exceptions.InvalidPath
```

### Does NOT Exist
- ~~`hvac.AsyncClient`~~ / any async hvac API: use `asyncio.to_thread`.
- ~~`VaultReader.url` / `VaultReader.token`~~: not stored today. This task adds `_url` / `_token_fp` only. **Never** store the raw token on the instance beyond what `hvac.Client` already holds.
- ~~`AbstractReader.aget`~~: don't add it.

---

## Complexity Contract

```json
{
  "schema_version": 1,
  "targets": [
    {"path": "navconfig/readers/vault.py", "action": "MODIFY"},
    {"path": "tests/test_vault_reader.py", "action": "CREATE"}
  ],
  "contract_symbols": [
    "sym:navconfig/readers/vault.py#VaultReader",
    "sym:navconfig/readers/vault.py#VaultReader.__init__",
    "sym:navconfig/readers/vault.py#VaultReader.get",
    "sym:navconfig/readers/vault.py#VaultReader.exists",
    "sym:navconfig/readers/vault.py#VaultReader.set",
    "sym:navconfig/readers/vault.py#VaultReader.delete",
    "sym:navconfig/readers/vault.py#VaultReader.list"
  ]
}
```

---

## Implementation Notes

### Key Constraints
- `_split_key`: `"a/b/KEY"` → `("a/b", "KEY")`. Both `"KEY"` and `"/KEY"` → `(self._env, "KEY")`.
- `_fetch_document` with an unsupported `self.version` raises `ValueError`, which propagates (not cached), matching `list()` today.
- Error logging: the transient errors that `get` and `exists` hit are logged at `logging.debug`, as today, and those in `list` at `logging.warning`.
- `aload(paths)`:
  - `paths` defaults to `[self._env]`.
  - It runs `asyncio.gather(*(asyncio.to_thread(self._read_document, p) for p in paths), return_exceptions=True)`.
  - It returns `{path: isinstance(result, dict)}`. An exception is logged as a warning and maps to `False`.
- `invalidate(path=None)` drops entries through a predicate that matches this reader's `url`, `token_fp`, `mount` and `version`, plus `path` when given.
- `refresh(path=None)` calls `invalidate(path or self._env)`, then returns `self.list(path or self._env)`.
- `pyproject.toml` has `filterwarnings = error`. Use `@pytest.mark.asyncio` and make sure no coroutine is left unawaited.

### Test fixture (decided)
```python
@pytest.fixture
def fake_hvac(monkeypatch):
    """monkeypatch hvac.Client -> FakeClient with:
    - is_authenticated() -> True
    - secrets.kv.v2.read_secret_version(path, mount_point): counts reads per path,
      returns {"data": {"data": deepcopy(store[path])}} or raises hvac.exceptions.InvalidPath
    - secrets.kv.v2.create_or_update_secret(path, secret, mount_point): store[path] = dict(secret)
    - an optional 'fail_next' flag that raises a generic Exception once (transient error)
    Also sets VAULT_TOKEN / VAULT_URL / VAULT_ENV via monkeypatch.setenv."""

@pytest.fixture(autouse=True)
def fresh_cache():
    from navconfig.readers import vault_cache
    vault_cache._reset_document_cache()
    yield
    vault_cache._reset_document_cache()
```

---

## Implementation Blueprint

### Steps (in order)
1. Add the imports and the `_url`, `_token_fp` and `_cache` attributes in `__init__`. *Why*: the cache key needs them.
2. Add `_split_key`, `_cache_key`, `_fetch_document` and `_read_document`. *Why*: this gives a single hvac read site.
3. Rewrite `get`, `exists` and `list` over `_read_document`. *Why*: goal G1, and AC "1 read".
4. Rewrite `set` and `delete` with `_split_key` and write-through `put`. *Why*: unified parsing and cache coherency.
5. Add `invalidate`, `refresh` and the async methods. *Why*: goals G3 and G5.
6. Write the tests.

### `navconfig/readers/vault.py` (MODIFY)
```python
# AFTER `from .abstract import AbstractReader` (verified: vault.py:6)
import asyncio
from typing import Dict, Iterable, Optional, Tuple, Union
from .vault_cache import MISSING, CacheKey, get_document_cache, token_fingerprint

# In __init__, AFTER `self._env = os.getenv("VAULT_ENV") or env or os.getenv("ENV", "")` (vault.py:33)
        self._url = url
        self._token_fp = token_fingerprint(token or "")
        self._cache = get_document_cache()

    def _split_key(self, key: str) -> Tuple[str, str]:
        """Split 'a/b/KEY' on the LAST '/'; bare keys resolve to self._env."""
        # FILL IN
    def _cache_key(self, path: str) -> CacheKey:
        return CacheKey(self._url, self._token_fp, self._mount, self.version, path)
    def _fetch_document(self, path: str) -> Union[dict, object]:
        # FILL IN: v1/v2 read; InvalidPath -> MISSING; other version -> ValueError
    def _read_document(self, path: str) -> Union[dict, object]:
        return self._cache.get_or_load(
            self._cache_key(path), lambda: self._fetch_document(path)
        )
```

### FILL IN checklist
- [ ] `get` / `exists` / `list`: keep their existing return contracts. Only the I/O path changes.
- [ ] `set` / `delete`: split on the last `/` and write the new document through to the cache.
- [ ] `aload`: `gather` with `return_exceptions=True`. It never raises.

---

## Acceptance Criteria

- [ ] `pytest tests/test_vault_reader.py -v` passes (10 tests).
- [ ] `exists()`, then `get()`, then `list()` on the same path results in exactly **1** `read_secret_version` call.
- [ ] Two `VaultReader()` instances with the same URL and token share reads. Different tokens don't.
- [ ] `list_paths` is unchanged, and `AbstractReader` is unchanged.
- [ ] The full `pytest` suite still passes.

---

## Validation Commands

- `pytest tests/test_vault_reader.py -q`
- `pytest tests/test_vault_cache.py -q`

---

## Test Specification

```python
# tests/test_vault_reader.py
def test_reader_get_exists_one_fetch(fake_hvac): ...
def test_reader_shared_cache_across_instances(fake_hvac): ...
def test_reader_different_token_not_shared(fake_hvac, monkeypatch): ...
def test_reader_missing_path_cached(fake_hvac): ...
def test_reader_transient_error_not_cached(fake_hvac): ...
def test_reader_split_key_last_slash(fake_hvac): ...
def test_reader_set_write_through(fake_hvac): ...
def test_reader_list_returns_copy(fake_hvac): ...
@pytest.mark.asyncio
async def test_reader_aget_aexists(fake_hvac): ...
@pytest.mark.asyncio
async def test_reader_aload_concurrent(fake_hvac): ...
```

---

## Agent Instructions

1. Work in `.claude/worktrees/feat-FEAT-001-async-vault-read`.
2. Check that TASK-001 is `"done"` in `sdd/tasks/.index.json`.
3. Verify the contract line numbers still match, set this task to `"in-progress"`, implement, validate, and commit only the listed files.
4. Move this file to `sdd/tasks/completed/`, set its index status to `"done"`, and fill in the Completion Note.

---

## Completion Note

*(Agent fills this in when done)*

**Completed by**:
**Date**:
**Notes**:

**Deviations from spec**:
