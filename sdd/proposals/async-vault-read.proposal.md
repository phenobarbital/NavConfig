---
id: FEAT-001
title: Cache Vault documents per path and support async Vault load + cache
slug: async-vault-read
type: feature
mode: enrichment
status: discussion
source:
  kind: inline
  jira_key: null
  jira_url: null
  fetched_at: 2026-09-29
  summary_oneline: Cache Vault documents by path, drop the remote exists()+get() double read, and check that async load + cache is feasible
overall_confidence: high
base_branch: main
projects: [navconfig]
tags: [vault, cache, async, performance]
research_state: null
created: 2026-09-29
updated: 2026-09-29
---

# FEAT-001: Cache Vault documents per path and support async Vault load + cache

> **Mode**: enrichment
> **Confidence**: high (localization), medium (async approach)
> **Source**: `inline`

---

## 0. Origin

> Navconfig: cachear documentos de Vault por ruta y evitar exists() + get()
> remotos, adicionalmente verificar que podemos hacer la carga + cache del
> vault de manera asíncrona

**Initial signals**:
- Verbs: "cachear", "evitar", "verificar", which point to a performance change plus a feasibility check.
- Named entities: Vault, `exists()`, `get()`, carga asíncrona (async loading).
- Acceptance criteria provided: none yet (see §5).

---

## 1. Synthesis Summary

A Kardex key lookup that misses `os.environ` and `_mapping_` goes through
`Kardex._get_external`. That method calls `reader.exists(key)` and then
`reader.get(key)` on every external reader. For `VaultReader`, each of those
calls is a separate HTTP request that downloads the **same whole KV document**
(`read_secret_version(path=...)`). One lookup therefore costs two remote reads,
and nothing is cached. Misses cost the same, so a key that isn't there hits
Vault twice every time it is requested. The proposal:
(a) cache each KV document in memory, keyed by `(mount, path)`, so that
`exists()`, `get()` and `list()` all read from one fetched copy;
(b) collapse `_get_external` into a single lookup;
(c) add an async load/prefetch path, which needs a transport decision
because `hvac` is synchronous.

---

## 2. Codebase Findings

### 2.1 Localization

| # | Path | Symbol | Role | Evidence |
|---|------|--------|------|----------|
| 1 | `navconfig/readers/vault.py` | `VaultReader.get` | Parses `path/key`, reads the full KV doc remotely, and returns one key | F001 |
| 2 | `navconfig/readers/vault.py` | `VaultReader.exists` | Duplicates `get`'s logic and does another full remote read | F001 |
| 3 | `navconfig/readers/vault.py` | `VaultReader.list` | Reads the full KV doc at `path`, and optionally filters it | F001 |
| 4 | `navconfig/readers/vault.py` | `set` / `delete` | Read-modify-write on the doc. The cache must be invalidated or updated here. | F001 |
| 5 | `navconfig/kardex.py` | `Kardex._get_external` | `exists(key)` followed by `get(key)`, which means 2 remote calls per lookup | F002 |
| 6 | `navconfig/kardex.py` | `Kardex.get` / `exists` / `__contains__` | Callers of `_get_external`. `exists()` goes through `_get_external`, so it costs 2 more calls. | F002 |
| 7 | `navconfig/kardex.py` | `_init_external_readers` | Builds `VaultReader(env=self.ENV)` when `VAULT_ENABLED` is set | F002 |
| 8 | `navconfig/loaders/vault.py` | `vaultLoader._load_from_vault` / `_init_vault_reader` | Startup bulk load through `VaultReader.list(path=vault_env)`. It builds a *second*, separate `VaultReader`. | F003 |

### 2.2 Constraints Discovered

- **Kardex is synchronous and initializes at import time.** `navconfig.config`
  is built when the module is imported, and every public accessor is sync.
  *Implication*: an async path has to be **additive** (an opt-in prefetch or
  `async` methods). It can't replace the sync API, and it can't require a
  running loop at import. *Evidence*: F002
- **`hvac` is sync-only** (it uses `requests` under the hood). Doing real async I/O
  means either `asyncio.to_thread(...)` around hvac, or calling the Vault
  HTTP API directly with `aiohttp`, which is already in the ecosystem. *Evidence*: F001
- **Key syntax overloading.** `get("a/b/KEY")` means doc `a/b` and field
  `KEY`. A bare `KEY` means doc `self._env` (VAULT_ENV > env > ENV).
  `set()` and `delete()` split on the *first* `/`, but `get()` and `exists()` split on the *last* one.
  That inconsistency affects how cache keys are computed. *Evidence*: F001
- **Secrets in memory.** Values are already copied into `os.environ` and
  `_mapping_` by the loader, so an in-process cache doesn't change the
  exposure surface. It should never be written to disk or to Redis. *Evidence*: F003
- **Two VaultReader instances.** The loader and the Kardex external reader
  each build their own reader, so a per-instance cache would fetch the same
  document twice at startup. *Evidence*: F002, F003

### 2.3 Recent History

| Commit | Message |
|--------|---------|
| `5dfb34c` | Make uvloop optional and lazy for Windows and support Python 3.14 |
| `c69acfa` | Reorganize kardex into sub-commands and fix the initialization order |
| `710ff7c` | Add VAULT_ENV to override the vault path segment independently of ENV |

No tests currently cover `VaultReader` or `_get_external`.

---

## 3. Probable Scope

### What's New

- **Per-path document cache in `VaultReader`**: stores
  `{(mount, path): (data | MISSING, fetched_at)}`, has an optional TTL
  (e.g. `VAULT_CACHE_TTL`), caches negative results (missing paths), and
  exposes `invalidate(path=None)` / `refresh()`.
- **Single internal `_read_document(path)`**: the one place that talks to
  Vault. `get`, `exists` and `list` all go through it.
- **Async load + cache**: something like `await reader.aload(paths)` /
  `await config.aload_vault()`, which pre-fills the cache concurrently.
  The transport (`to_thread` vs. `aiohttp`) is still open, see §5.

### What Changes

- **`VaultReader.get` / `exists` / `list`**: served from the cache, and the
  duplicated parsing moves into one helper.
- **`VaultReader.set` / `delete`**: update or invalidate the cached document
  after the write.
- **`Kardex._get_external`**: one call per reader, e.g. `get(key, default=_SENTINEL)`,
  instead of `exists()` followed by `get()`.
- **`vaultLoader`**: could share or seed the Kardex reader's cache so the
  startup bulk load isn't repeated.

### What's Untouched (Non-Goals)

- Public sync API of `Kardex` (`config.get`, `config.KEY`, `in`).
- The Redis reader's behavior.
- Vault authentication methods (token only). AppRole etc. are out of scope.
- Persisting the cache outside process memory.

### Integration Risks

- **Stale secrets** after rotation in Vault. *Mitigation*: TTL,
  explicit `invalidate()`, and no TTL by default only if you agree to that (§5).
- **`__contains__` bug**: it returns after the *first* reader
  (`return val is True` inside the loop). It's worth fixing while in there.
- **Thread-safety**: the cache is a dict shared across threads, so it needs a lock
  or an idempotent fill pattern.

---

## 4. Confidence Map

| ID | Claim | Evidence | Confidence |
|----|-------|----------|------------|
| C1 | `_get_external` does `exists()` then `get()`, i.e. 2 remote reads per lookup | F002 (kardex.py `_get_external`) | high |
| C2 | `exists()` and `get()` each download the whole KV document | F001 | high |
| C3 | There is no caching at all in `VaultReader` | F001 | high |
| C4 | Misses are re-fetched every time | F001, F002 | high |
| C5 | `hvac` has no async API, so async needs to_thread or direct HTTP | library knowledge | medium |
| C6 | Loader and Kardex hold separate `VaultReader` instances | F002, F003 | high |

Distribution: **5** high, **1** medium, **0** low.

---

## 5. Open Questions

### Resolved (during proposal phase)

- [x] **Cache freshness**: *Resolved*: configurable TTL via `VAULT_CACHE_TTL`
  (default e.g. 300s; `0` = process lifetime), plus manual `invalidate()` / `refresh()`.
- [x] **Async transport**: *Resolved*: `asyncio.to_thread` wrapping the existing
  hvac client. No new dependencies and a single KV v1/v2 code path.
- [x] **Async entry point**: *Resolved*: both an explicit prefetch
  (`await config.aload_vault(paths)` for `on_startup`) and lazy async getters
  (`await config.aget(key)` / `aexists(key)`).
- [x] **Cache scope**: *Resolved*: shared at module level, keyed by
  `(url, mount, path)`, so that the loader and Kardex reuse the same documents.
- [x] **Negative caching**: *Resolved*: yes. Missing paths/keys are cached with the same TTL.

### Unresolved (defer to spec)

- [ ] **Default TTL value**: is 300s acceptable? *Owner*: tbd
- [ ] **Concurrent miss de-duplication**: should concurrent `aget()` calls for the same path
  share one in-flight fetch (per-path lock / future)? The recommendation is yes.

---

## 6. Recommended Next Step

**`/sdd-spec FEAT-001`**, once the open questions in §5 are answered.
Localization is high-confidence and the sync part (cache + single lookup)
is well-bounded. The async part is additive.

### Parallelism

**Mixed**: (1) the sync per-path cache and the `_get_external` single lookup, and
(2) the async load/prefetch, are separable. (2) builds on the cache from (1),
so it should run sequentially in the same worktree (per-spec).

---

## 7. Research Audit

| Finding | Description |
|---------|-------------|
| F001 | `navconfig/readers/vault.py`, a full read of `VaultReader` |
| F002 | `navconfig/kardex.py`: `_init_external_readers`, `_get_external`, `get`, `exists`, `__contains__` |
| F003 | `navconfig/loaders/vault.py`: `_load_from_vault`, `_init_vault_reader` |

---

## 8. Provenance

| Field | Value |
|-------|-------|
| Generated by | `/sdd-proposal` |
| Template | `ai-parrot/sdd/templates/proposal.md` (navconfig has no `sdd/templates/` yet) |
| Operator | Claude Code |
