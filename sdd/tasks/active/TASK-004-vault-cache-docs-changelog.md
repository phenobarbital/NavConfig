# TASK-004: Docs + CHANGELOG for Vault cache & async API

**Feature**: FEAT-001 — Vault Document Cache & Async Vault Read
**Spec**: `sdd/specs/async-vault-read.spec.md`
**Status**: pending
**Priority**: medium
**Estimated effort**: S (< 2h)
**Depends-on**: TASK-003
**Assigned-to**: unassigned

---

## Context

Implements the documentation part of spec §3 **Module 4**, and closes the remaining
acceptance criteria in spec §5:
- `VAULT_CACHE_TTL` is documented;
- there's a CHANGELOG entry;
- a final end-to-end check that the full suite passes.

---

## Scope

- Document these in `docs/config.rst`, next to the existing Vault/`VAULT_*` settings (check with `grep -n VAULT docs/*.rst`):
  - `VAULT_CACHE_TTL`: float seconds, default `300`, `0` means never expire.
  - Negative caching: a newly created secret is invisible until the TTL passes, `set()` runs, or `invalidate()` is called.
  - `invalidate_vault_cache()` and `reload_current_env()`.
  - The async API: `await config.aload_vault([...])` from `on_startup`, and `await config.aget(...)` / `aexists(...)`.
- Add a CHANGELOG entry in an `## [Unreleased]` section at the top of `CHANGELOG.md`, in Keep a Changelog format:
  - **Added**: the Vault document cache, `VAULT_CACHE_TTL`, the async API, and `invalidate`/`refresh`.
  - **Changed**:
    - `_get_external` makes a single read.
    - `VaultReader.set`/`delete` now split nested keys on the **last** `/`. This is a behavior change for `a/b/KEY`.
  - **Fixed**: `Kardex.__contains__` now checks all readers.
- Run the full `pytest` suite and save the output to `artifacts/logs/FEAT-001-pytest.log`.

**NOT in scope**:
- Any code change.
- Version bumps. `navconfig/version.py` says `2.5.2`, but `CHANGELOG.md` already has `[3.0.0]`. **Flag this mismatch to the user** and let the release decide the version, so keep the entry as `[Unreleased]`.

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `docs/config.rst` | MODIFY | Vault cache + async API docs |
| `CHANGELOG.md` | MODIFY | Unreleased entry |

---

## Codebase Contract (Anti-Hallucination)

### Verified Imports
None. This task is docs only.

### Existing Signatures to Use
```text
CHANGELOG.md:1   "# Changelog"; Keep a Changelog format; latest section "## [3.0.0] - 2026-08-21" (line 8)
docs/config.rst  existing reStructuredText config reference
navconfig/version.py  __version__ = "2.5.2"
```

### Does NOT Exist
- ~~`docs/vault.rst`~~: doesn't exist. Don't create a new page unless `docs/config.rst` has no Vault section, and if you do, add it to the `docs/index.rst` toctree.

---

## Complexity Contract

```json
{
  "schema_version": 1,
  "targets": [
    {"path": "docs/config.rst", "action": "MODIFY"},
    {"path": "CHANGELOG.md", "action": "MODIFY"}
  ],
  "contract_symbols": []
}
```

---

## Acceptance Criteria

- [ ] `VAULT_CACHE_TTL` and the async API are documented in `docs/config.rst`.
- [ ] `CHANGELOG.md` has an `[Unreleased]` entry covering the cache, the async API, the `__contains__` fix, and the key-parsing change.
- [ ] The full `pytest` suite passes, and its log is saved to `artifacts/logs/FEAT-001-pytest.log`.
- [ ] Every checkbox in spec §5 is verified.

---

## Validation Commands

- `pytest tests/test_vault_cache.py tests/test_vault_reader.py tests/test_kardex_vault.py -q`
- `pytest -q`

---

## Agent Instructions

1. Work in `.claude/worktrees/feat-FEAT-001-async-vault-read`.
2. Check that TASK-003 is `"done"`.
3. Update the docs, run the full suite, and commit only the listed files.
4. Move this file to `sdd/tasks/completed/`, set its index status to `"done"`, and fill in the Completion Note.
5. Tell the user about the `version.py` / `CHANGELOG` version mismatch.

---

## Completion Note

*(Agent fills this in when done)*

**Completed by**:
**Date**:
**Notes**:

**Deviations from spec**:
