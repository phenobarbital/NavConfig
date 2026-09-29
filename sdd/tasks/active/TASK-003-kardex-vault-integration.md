# TASK-003: Kardex integration (single-get lookup, __contains__ fix, async API)

**Feature**: FEAT-001 — Vault Document Cache & Async Vault Read
**Spec**: `sdd/specs/async-vault-read.spec.md`
**Status**: pending
**Priority**: high
**Estimated effort**: M (2-4h)
**Depends-on**: TASK-002
**Assigned-to**: unassigned

---

## Context

Implements spec §3 **Module 3**. `Kardex._get_external` currently calls
`reader.exists(key)` and then `reader.get(key)`, which is 2 remote reads.
`__contains__` returns after checking only the first reader. This task:
- collapses the lookup into one `get()` (goal G2);
- fixes `__contains__` (goal G7);
- exposes the async API and cache invalidation on the config object (goals G3 and G5).

---

## Scope

- `_get_external`: for each enabled reader, `val = reader.get(key)`, and return it if it isn't `None`. Keep `except RuntimeError: continue`, and never call `exists()`.
- `__contains__`: check environ and `_mapping_` first, then return `True` if **any** enabled reader's `exists(key)` is `True`. Catch `RuntimeError` per reader.
- Add these methods:
  - `async aget(key, section=None, fallback=None)`: the same resolution order as `get()`. For the external step, use `await reader.aget(key)` when `hasattr(reader, "aget")`, and otherwise `await asyncio.to_thread(reader.get, key)`. Then apply `_unserialize`.
  - `async aexists(key)`.
  - `async aload_vault(paths=None)`: delegates to `self._readers["vault"].aload(paths)` when vault is enabled, and returns `{}` otherwise.
  - `invalidate_vault_cache(path=None)`: delegates to the vault reader's `invalidate()`, and is a no-op otherwise.
- `reload_current_env`: call `self.invalidate_vault_cache()` before `set_env(..., reload=True)`.
- Write `tests/test_kardex_vault.py` covering the 4 M3 tests in spec §4.

**NOT in scope**:
- The truthiness check in `Kardex.get` (`if val := self._get_external(key)`). Keep it as is.
- `set_env()` invalidation. The spec §8 decision is no.
- Loader changes.
- Docs.

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `navconfig/kardex.py` | MODIFY | Single-get, `__contains__` fix, async API, invalidation |
| `tests/test_kardex_vault.py` | CREATE | Unit tests for M3 |

---

## Codebase Contract (Anti-Hallucination)

### Verified Imports
```python
import asyncio                     # navconfig/kardex.py:9 (already imported)
import logging                     # navconfig/kardex.py:12
from .readers.vault import VaultReader   # navconfig/kardex.py:37 (try/except; bound as HVAULT_LOADER)
```

### Existing Signatures to Use
```python
# navconfig/kardex.py
class Kardex:
    _readers: dict = {}                     # line 51 — CLASS-level; "redis" may alias "cache"
    _mapping_: dict = {}                    # line 52
    def _init_external_readers(self)        # line 183; vault stored at self._readers["vault"] (line 217)
    #   self._use_vault: bool               # line 214
    def _get_external(self, key: str) -> Any        # line 396
    def get(self, key, section=None, fallback=None) -> Any  # line 496 (resolution order to mirror)
    def __contains__(self, key: str) -> bool        # line 538 (BUG: returns inside loop)
    def exists(self, key: str) -> bool              # line 547 (uses _get_external)
    def _unserialize(self, value: Any) -> str       # line 583
    def reload_current_env(self)                    # line 790

# navconfig/readers/redis.py
class mredis(AbstractReader):
    def get(self, key)            # returns None on miss
    def exists(self, key, *keys)  # line 60

# navconfig/readers/vault.py (after TASK-002)
VaultReader.aget / aexists / aload / invalidate
```

### Does NOT Exist
- ~~`Kardex.aget` / `aexists` / `aload_vault` / `invalidate_vault_cache`~~: this task creates them.
- ~~`mredis.aget`~~: doesn't exist, so fall back to `asyncio.to_thread(reader.get, key)`.
- ~~`AbstractReader.aget`~~: don't add it. Use `hasattr`.

---

## Complexity Contract

```json
{
  "schema_version": 1,
  "targets": [
    {"path": "navconfig/kardex.py", "action": "MODIFY"},
    {"path": "tests/test_kardex_vault.py", "action": "CREATE"}
  ],
  "contract_symbols": [
    "sym:navconfig/kardex.py#Kardex",
    "sym:navconfig/kardex.py#Kardex._get_external",
    "sym:navconfig/kardex.py#Kardex.get",
    "sym:navconfig/kardex.py#Kardex.__contains__",
    "sym:navconfig/kardex.py#Kardex.exists",
    "sym:navconfig/kardex.py#Kardex._unserialize",
    "sym:navconfig/kardex.py#Kardex.reload_current_env"
  ]
}
```

---

## Implementation Notes

### Key Constraints
- `Kardex` is a Singleton, and `_readers` is class-level. In tests, `monkeypatch.setitem(Kardex._readers, ...)` / `monkeypatch.setattr(config, "_readers", {...})` is enough to isolate them. Don't construct a new Kardex.
- Fake readers in the tests are plain objects with `enabled = True`, and with `get`/`exists` counters. That means TASK-003 tests don't need `fake_hvac`.
- Use `getattr(self, "_use_vault", False)` and `self._readers.get("vault")`, because `_init_external_readers` may not have set `vault`.
- `filterwarnings = error`: every coroutine must be awaited.

---

## Implementation Blueprint

### `navconfig/kardex.py` (MODIFY)
```python
# REPLACE body of `def _get_external(self, key: str) -> Any:` (kardex.py:396)
        """Get a value from the external readers (a single get() per reader)."""
        for _, reader in self._readers.items():
            try:
                if reader.enabled is True:
                    val = reader.get(key)
                    if val is not None:
                        return val
            except RuntimeError:
                continue
        return None

# REPLACE body of `def __contains__(self, key: str) -> bool:` (kardex.py:538)
        # FILL IN: environ/_mapping_ -> True; any(enabled reader.exists(key)) with RuntimeError guard

# ADD after `def exists` (kardex.py:547) — async API
    async def aget(self, key: str, section: Optional[str] = None, fallback: Any = None) -> Any:
        # FILL IN: mirror get(); external step via reader.aget or asyncio.to_thread(reader.get, key)
    async def aexists(self, key: str) -> bool:
        # FILL IN
    async def aload_vault(self, paths: Optional[Iterable[str]] = None) -> Dict[str, bool]:
        # FILL IN
    def invalidate_vault_cache(self, path: Optional[str] = None) -> None:
        # FILL IN

# MODIFY `def reload_current_env(self):` (kardex.py:790)
        self.invalidate_vault_cache()
        self.set_env(self._current_env, reload=True)
```

### FILL IN checklist
- [ ] Check that `Iterable` and `Dict` are imported in the `typing` block at `kardex.py:1`, and add them if missing.
- [ ] `aget`: identical resolution order to `get()`, including `section` handling.

---

## Acceptance Criteria

- [ ] `pytest tests/test_kardex_vault.py -v` passes (4 tests).
- [ ] With a fake reader, `config.get("X")` calls `reader.get` once and `reader.exists` never.
- [ ] `"X" in config` is `True` when only the second reader has X.
- [ ] The full `pytest` suite passes, including the existing `tests/test_config.py`.

---

## Validation Commands

- `pytest tests/test_kardex_vault.py -q`
- `pytest tests/test_config.py -q`

---

## Test Specification

```python
# tests/test_kardex_vault.py
def test_kardex_get_external_single_call(monkeypatch): ...
def test_kardex_contains_checks_all_readers(monkeypatch): ...
@pytest.mark.asyncio
async def test_kardex_aget_resolution_order(monkeypatch): ...
@pytest.mark.asyncio
async def test_kardex_aload_vault_disabled(monkeypatch): ...
```

---

## Agent Instructions

1. Work in `.claude/worktrees/feat-FEAT-001-async-vault-read`.
2. Check that TASK-002 is `"done"` in `sdd/tasks/.index.json`.
3. Verify the contract, set this task to `"in-progress"`, implement, validate, and commit only the listed files.
4. Move this file to `sdd/tasks/completed/`, set its index status to `"done"`, and fill in the Completion Note.

---

## Completion Note

*(Agent fills this in when done)*

**Completed by**:
**Date**:
**Notes**:

**Deviations from spec**:
