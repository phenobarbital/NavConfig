---
type: feature
base_branch: main
projects: [navconfig]
tags: [vault, cache, async, performance]
---

# Feature Specification: Vault Document Cache & Async Vault Read

**Feature ID**: FEAT-001
**Date**: 2026-09-29
**Author**: Jesus Lara (with Claude Code)
**Status**: draft
**Target version**: 2.6.0
**Proposal**: `sdd/proposals/async-vault-read.proposal.md`

---

## 1. Motivation & Business Requirements

### Problem Statement

When a Kardex lookup misses both `os.environ` and `_mapping_`, it falls through
to `Kardex._get_external`, which calls `reader.exists(key)` and then
`reader.get(key)`. For `VaultReader`, each of those calls is its own HTTP round trip
that downloads the **whole** KV document at the resolved path. The consequences:

- Every external lookup costs **2 remote reads** of the same document.
- `Kardex.exists()` costs 2 more, because it also goes through `_get_external`.
- Nothing is cached, so a key that doesn't exist hits Vault twice on *every*
  access.
- `vaultLoader` and the Kardex external reader each create their own
  `VaultReader`, so the same document is fetched twice at startup.
- The only way to talk to Vault is synchronously (`hvac` is sync-only). Async apps
  (navigator/aiohttp) block the event loop on Vault I/O and can't prefetch
  secrets concurrently during `on_startup`.

### Goals

- G1: At most **one** remote read per `(vault, mount, path)` within the TTL, shared
  across all `VaultReader` instances in the process.
- G2: `_get_external` makes a single `get()` call per reader, with no `exists()` + `get()` pair.
- G3: Configurable TTL (`VAULT_CACHE_TTL`, default 300s, `0` = never expire),
  plus explicit `invalidate()` / `refresh()`.
- G4: Missing documents (`InvalidPath`) are negatively cached with the same TTL.
  Transient errors are **never** cached.
- G5: Async API: `await config.aload_vault(paths)` for prefetching, plus
  `await config.aget(key)` / `await config.aexists(key)`. Both are implemented with
  `asyncio.to_thread` over the existing hvac client.
- G6: Concurrent misses on the same path (sync threads or async tasks) share a
  single in-flight fetch (single-flight).
- G7: Fix `Kardex.__contains__` so it checks every reader, not only the first.

### Non-Goals

- Changing the synchronous public API of `Kardex` (`get`, `__getattr__`, `in`, `exists`).
- A native `aiohttp` Vault client. The transport stays hvac.
- Vault auth methods other than token (AppRole, K8s, …).
- Persisting the cache outside process memory (no disk, no Redis).
- Changes to the Redis reader.

---

## 2. Architectural Design

### Overview

A new module-level `VaultDocumentCache` (thread-safe, TTL, negative entries,
per-key single-flight lock) stores whole KV documents. Its key is
`(url, token_fingerprint, mount, kv_version, path)`, so readers pointing at
the same Vault with the same token share entries, and different tokens (which
may have different ACLs) never do.

`VaultReader` gets a single fetch point, `_read_document(path)`, that goes through the
cache. `get`, `exists` and `list` all read through it. `set` and `delete` write
through and then store the new document in the cache. The async methods are thin
`asyncio.to_thread` wrappers over the same sync code path. Because the cache locks
are `threading` primitives, sync and async callers share one consistent cache.

Kardex's `_get_external` switches to a single `get()`. New `aget`, `aexists`
and `aload_vault` methods, plus `invalidate_vault_cache`, are added.
`vaultLoader` needs no code change: its `VaultReader.list()` call fills the
shared cache, and the Kardex reader then reuses it.

### Component Diagram
```
Kardex.get / exists / __contains__ ──→ _get_external ──→ reader.get(key)   (1 call)
Kardex.aget / aexists / aload_vault ─→ VaultReader.aget / aexists / aload
                                              │ asyncio.to_thread
                                              ▼
vaultLoader._load_from_vault ──→ VaultReader.get / exists / list / set / delete
                                              │
                                              ▼
                                   VaultReader._read_document(path)
                                              │
                                              ▼
                              VaultDocumentCache (module singleton)
                                  hit ─→ dict | MISSING
                                  miss ─→ per-key lock ─→ _fetch_document (hvac, 1 HTTP)
```

### Integration Points

| Existing Component | Integration Type | Notes |
|---|---|---|
| `navconfig.readers.vault.VaultReader` | modifies | Reads go through the cache; adds async methods and `invalidate()` |
| `navconfig.kardex.Kardex` | modifies | Single-call `_get_external`, `__contains__` fix, async API, cache invalidation |
| `navconfig.loaders.vault.vaultLoader` | uses (no change) | Its `list()` call now fills the shared cache |
| `navconfig.readers.abstract.AbstractReader` | unchanged | No new abstract methods, so the Redis reader is unaffected |

### Data Models

navconfig does **not** depend on pydantic. Use stdlib `dataclasses` (no new deps).

```python
MISSING: Final = object()  # negative-cache marker (path does not exist)

@dataclass(frozen=True)
class CacheKey:
    url: str
    token_fp: str      # sha256(token)[:16], so the raw token is never stored in the key
    mount: str
    version: int
    path: str

@dataclass
class CacheEntry:
    data: Union[dict, object]   # dict of the KV document, or MISSING
    fetched_at: float           # time.monotonic()
```

### New Public Interfaces
```python
# navconfig/readers/vault.py
class VaultReader(AbstractReader):
    def invalidate(self, path: Optional[str] = None) -> None: ...
    def refresh(self, path: Optional[str] = None) -> dict: ...
    async def aget(self, key: str, default: Any = None, sub_key: Optional[str] = None) -> Any: ...
    async def aexists(self, key: str) -> bool: ...
    async def alist(self, path: Optional[str] = None, filter: Optional[str] = None) -> dict: ...
    async def aload(self, paths: Optional[Iterable[str]] = None) -> Dict[str, bool]: ...

# navconfig/kardex.py
class Kardex:
    async def aget(self, key: str, section: Optional[str] = None, fallback: Any = None) -> Any: ...
    async def aexists(self, key: str) -> bool: ...
    async def aload_vault(self, paths: Optional[Iterable[str]] = None) -> Dict[str, bool]: ...
    def invalidate_vault_cache(self, path: Optional[str] = None) -> None: ...
```

---

## 3. Module Breakdown

#### Delegation-eligible modules

| Module | Eligible? | Decided patterns / exact contracts | Why not (if no) |
|---|---|---|---|
| M1: VaultDocumentCache | yes | Key/entry dataclasses, TTL semantics, single-flight via per-key `threading.Lock`, module singleton | — |
| M2: VaultReader refactor | yes | `_split_key` = last `/`; cache-through reads; write-through set/delete; `to_thread` async | — |
| M3: Kardex integration | yes | Single `get()` in `_get_external`; async methods listed in §2 | — |
| M4: Tests & docs | yes | Fake hvac client counting calls; `@pytest.mark.asyncio` | — |

### Module 1: VaultDocumentCache
- **Path**: `navconfig/readers/vault_cache.py` (new)
- **Responsibility**: A thread-safe, process-wide TTL cache of KV documents with
  negative entries and single-flight loading.
- **Depends on**: stdlib only (`threading`, `time`, `hashlib`, `dataclasses`).
- **Interface Skeleton**:
  ```python
  # navconfig/readers/vault_cache.py  (new)
  MISSING: Final[object]

  def token_fingerprint(token: str) -> str:
      """Return sha256(token) hex truncated to 16 chars."""

  class VaultDocumentCache:
      """Process-wide cache of Vault KV documents keyed by CacheKey."""
      def __init__(self, ttl: float = 300.0) -> None:
          """ttl <= 0 means entries never expire."""
      @property
      def ttl(self) -> float: ...
      def get_or_load(self, key: CacheKey, loader: Callable[[], Union[dict, object]]) -> Union[dict, object]:
          """Return a fresh cached value, or call loader() under a per-key lock (single-flight).
          loader returns a dict, or MISSING when the path doesn't exist. Exceptions raised by
          loader propagate and are NOT cached."""
      def put(self, key: CacheKey, data: Union[dict, object]) -> None:
          """Store/replace an entry (used by set/delete write-through)."""
      def invalidate(self, predicate: Optional[Callable[[CacheKey], bool]] = None) -> int:
          """Drop matching entries (all when predicate is None). Returns count dropped."""

  def get_document_cache() -> VaultDocumentCache:
      """Module singleton; TTL read once from VAULT_CACHE_TTL (float seconds, default 300)."""
  ```

### Module 2: VaultReader refactor
- **Path**: `navconfig/readers/vault.py` (modifies)
- **Responsibility**: Route every read through the cache, unify key parsing,
  write-through on `set`/`delete`, and add the async wrappers.
- **Depends on**: Module 1
- **Interface Skeleton**:
  ```python
  class VaultReader(AbstractReader):
      def __init__(self, env: str = None) -> None:
          """Unchanged behavior; additionally stores self._url, self._token_fp, self._cache."""
      def _split_key(self, key: str) -> Tuple[str, str]:
          """'a/b/KEY' -> ('a/b', 'KEY'); 'KEY' or '/KEY' -> (self._env, 'KEY'). Splits on LAST '/'."""
      def _cache_key(self, path: str) -> CacheKey: ...
      def _fetch_document(self, path: str) -> Union[dict, object]:
          """One hvac read (kv v1/v2). Returns dict, or MISSING on hvac.exceptions.InvalidPath.
          Any other exception propagates (never cached)."""
      def _read_document(self, path: str) -> Union[dict, object]:
          """self._cache.get_or_load(self._cache_key(path), lambda: self._fetch_document(path))."""
      def get(self, key, default=None, path="secrets", sub_key=None) -> Any:
          """Same signature and return semantics as today; served from _read_document.
          Transient errors -> log at debug level and return default (unchanged behavior)."""
      def exists(self, key: str) -> bool: ...
      def list(self, path: str = None, filter: str = None) -> dict:
          """Returns a shallow COPY of the cached document (callers must not mutate the cache)."""
      def set(self, key: str, value: Any, **kwargs) -> None:
          """Read-modify-write as today, then cache.put(new document)."""
      def delete(self, key: str, secret_path: str = None) -> bool:
          """As today, then cache.put(new document)."""
      def invalidate(self, path: Optional[str] = None) -> None:
          """Drop this reader's entries (same url/token/mount/version); one path, or all."""
      def refresh(self, path: Optional[str] = None) -> dict:
          """invalidate(path) and re-read it (path defaults to self._env)."""
      async def aget(...) -> Any:   # asyncio.to_thread(self.get, ...)
      async def aexists(...) -> bool:
      async def alist(...) -> dict:
      async def aload(self, paths=None) -> Dict[str, bool]:
          """Prefetch paths concurrently (asyncio.gather over to_thread(_read_document)).
          paths defaults to [self._env]. Returns {path: found}. A failing path logs a warning
          and maps to False; it does not raise."""
  ```

### Module 3: Kardex integration
- **Path**: `navconfig/kardex.py` (modifies)
- **Responsibility**: Single-call external lookup, fix `__contains__`, and expose the async API
  and cache invalidation.
- **Depends on**: Module 2
- **Interface Skeleton**:
  ```python
  def _get_external(self, key: str) -> Any:
      """For each enabled reader: val = reader.get(key); return val if not None.
      Keeps the existing `except RuntimeError: continue`. No exists() call."""
  def __contains__(self, key: str) -> bool:
      """environ/_mapping_ first, then any(reader.exists(key)) across ALL enabled readers."""
  async def aget(self, key, section=None, fallback=None) -> Any:
      """Same resolution order as get(). The external step awaits reader.aget when present,
      otherwise asyncio.to_thread(reader.get, key). Applies _unserialize like get()."""
  async def aexists(self, key: str) -> bool: ...
  async def aload_vault(self, paths=None) -> Dict[str, bool]:
      """Delegates to self._readers['vault'].aload(paths) when vault is enabled; else {}."""
  def invalidate_vault_cache(self, path: Optional[str] = None) -> None:
      """Delegates to the vault reader's invalidate(); no-op when vault is disabled."""
  def reload_current_env(self):
      """Now calls invalidate_vault_cache() before set_env(..., reload=True)."""
  ```

### Module 4: Tests & docs
- **Path**: `tests/test_vault_cache.py`, `tests/test_vault_reader.py`,
  `tests/test_kardex_vault.py` (new); `docs/` + `CHANGELOG.md` (modifies)
- **Responsibility**: Unit tests with a fake hvac client that counts reads. Document
  `VAULT_CACHE_TTL` and the async API.
- **Depends on**: Modules 1–3

---

## 4. Test Specification

### Unit Tests
| Test | Module | Description |
|---|---|---|
| `test_cache_hit_within_ttl` | M1 | The second `get_or_load` doesn't call the loader |
| `test_cache_expires_after_ttl` | M1 | Monkeypatched `time.monotonic`, so the loader is called again after the TTL |
| `test_cache_ttl_zero_never_expires` | M1 | `ttl=0` → never reloads |
| `test_cache_negative_entry` | M1 | `MISSING` is cached; the loader is called once |
| `test_cache_exception_not_cached` | M1 | The loader raises → the next call retries |
| `test_cache_single_flight_threads` | M1 | N threads missing the same key → the loader is called once |
| `test_cache_invalidate_predicate` | M1 | Only matching keys are dropped |
| `test_reader_get_exists_one_fetch` | M2 | `exists()`, `get()` and `list()` on one path → 1 hvac read |
| `test_reader_shared_cache_across_instances` | M2 | Two readers with the same url/token → 1 read |
| `test_reader_different_token_not_shared` | M2 | Different tokens → separate reads |
| `test_reader_missing_path_cached` | M2 | `InvalidPath` → `default`/`False`, and 1 read across repeats |
| `test_reader_transient_error_not_cached` | M2 | Generic exception → `default`, then retried |
| `test_reader_split_key_last_slash` | M2 | `set`, `get` and `delete` agree on `a/b/KEY` |
| `test_reader_set_write_through` | M2 | After `set`, `get` returns the new value with no extra read |
| `test_reader_list_returns_copy` | M2 | Mutating the result of `list()` doesn't affect the cache |
| `test_reader_aget_aexists` | M2 | Async wrappers return the same results as the sync ones |
| `test_reader_aload_concurrent` | M2 | `aload(['a','b','missing'])` → `{'a':True,'b':True,'missing':False}`, 1 read each |
| `test_kardex_get_external_single_call` | M3 | Fake reader: `get` called once, `exists` never |
| `test_kardex_contains_checks_all_readers` | M3 | A key found only in the second reader → `True` |
| `test_kardex_aget_resolution_order` | M3 | `_mapping_` > environ > readers, same as `get()` |
| `test_kardex_aload_vault_disabled` | M3 | Vault not enabled → `{}` |

### Test Data / Fixtures
```python
@pytest.fixture
def fake_hvac(monkeypatch):
    """Patch hvac.Client with an in-memory KV store that counts read calls
    and raises hvac.exceptions.InvalidPath for unknown paths."""

@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    """Reset the module singleton between tests."""
```

No real Vault is required. `@pytest.mark.asyncio` goes on async tests (pytest-asyncio
is already a dev dependency).

---

## 5. Acceptance Criteria

- [ ] `pytest` passes, including all the new tests in §4.
- [ ] A `Kardex.get()` of a Vault-only key performs **1** hvac read (was 2), and 0 on
      a repeat within the TTL.
- [ ] `Kardex.exists()` / `in` on a missing key performs at most 1 hvac read per path
      per TTL window.
- [ ] Startup (`vaultLoader` + Kardex vault reader) reads `{mount}/{VAULT_ENV}` once.
- [ ] `await config.aload_vault([...])` prefetches without blocking the event loop.
      After that, sync `config.get()` performs 0 hvac reads.
- [ ] `VAULT_CACHE_TTL` is documented. `0` disables expiry.
- [ ] No breaking changes to the sync public API. `AbstractReader` is unchanged.
- [ ] `CHANGELOG.md` has an entry covering the cache, the async API, the `__contains__` fix, and
      the unified key parsing in `set`/`delete`.

---

## 6. Codebase Contract

### Verified Imports
```python
import hvac                                          # navconfig/readers/vault.py:4
from navconfig.exceptions import ReaderNotSet        # used at navconfig/readers/vault.py:5
from navconfig.readers.abstract import AbstractReader  # navconfig/readers/abstract.py
from navconfig.readers.vault import VaultReader      # navconfig/kardex.py:37 (relative import)
```

### Existing Class Signatures
```python
# navconfig/readers/vault.py
class VaultReader(AbstractReader):
    def __init__(self, env: str = None) -> None            # reads VAULT_URL, VAULT_TOKEN, VAULT_VERSION,
                                                            # VAULT_MOUNT_POINT, VAULT_ENV; sets self.client,
                                                            # self.version, self._mount, self._env, self.enabled
    def get(self, key: str, default: Any = None, path: str = "secrets", sub_key: str = None) -> Any
    def exists(self, key: str) -> bool
    def set(self, key: str, value: Any, **kwargs) -> None  # splits key on FIRST '/' today
    def delete(self, key: str, secret_path: str = None) -> bool  # splits on FIRST '/' today
    def list(self, path: str = None, filter: str = None) -> dict
    def list_paths(self, path: str = None) -> list          # untouched

# navconfig/readers/redis.py
class mredis(AbstractReader):
    def get(self, key)            # returns None on miss, so it's compatible with the single-get _get_external
    def exists(self, key, *keys)

# navconfig/kardex.py
class Kardex:
    _readers: dict = {}           # CLASS-level dict (line 51)
    def _init_external_readers(self)                          # line 183
    def _get_external(self, key: str) -> Any                  # line 396
    def get(self, key: str, section: str = None, fallback: Any = None) -> Any  # line 496
    def __contains__(self, key: str) -> bool                  # line 538
    def exists(self, key: str) -> bool                        # line 547
    def reload_current_env(self)                              # line 790

# navconfig/loaders/vault.py
class vaultLoader(BaseLoader):
    def _load_from_vault(self) -> Dict[str, Any]              # calls self.vault_reader.list(path=self.vault_env)
    def _init_vault_reader(self) -> None                      # builds its own VaultReader(env=self.vault_env)
```

### Integration Points
| New Component | Connects To | Via | Verified At |
|---|---|---|---|
| `VaultDocumentCache` | `VaultReader._read_document` | `get_or_load` | new |
| `VaultReader.aget` etc. | `VaultReader.get` etc. | `asyncio.to_thread` | new |
| `Kardex.aload_vault` | `self._readers["vault"]` | `.aload()` | `kardex.py:217` |
| `vaultLoader` | shared cache | `VaultReader.list()` | `loaders/vault.py:222` |

### Does NOT Exist (Anti-Hallucination)
- ~~`hvac.AsyncClient`~~ / any async hvac API: does not exist.
- ~~`pydantic`~~: not a navconfig dependency. Use `dataclasses`.
- ~~`VaultReader.url` / `VaultReader.token`~~: not stored today. M2 adds `_url` / `_token_fp`.
- ~~`Kardex.aget` / `aexists` / `aload_vault` / `invalidate_vault_cache`~~: don't exist yet.
- ~~`AbstractReader.aget`~~: don't add it. Kardex feature-detects with `hasattr`.

### Edit Sites (Blueprint Anchors)

Verified against: `1e6516d`

| File | Action | Verbatim anchor line | Verified at | Occurrences |
|---|---|---|---|---|
| `navconfig/readers/vault_cache.py` | CREATE | — | — | — |
| `navconfig/readers/vault.py` | MODIFY | `class VaultReader(AbstractReader):` | `vault.py:14` | 1 |
| `navconfig/kardex.py` | MODIFY | `def _get_external(self, key: str) -> Any:` | `kardex.py:396` | 1 |
| `navconfig/kardex.py` | MODIFY | `def __contains__(self, key: str) -> bool:` | `kardex.py:538` | 1 |
| `navconfig/kardex.py` | MODIFY | `def reload_current_env(self):` | `kardex.py:790` | 1 |
| `tests/test_vault_cache.py` | CREATE | — | — | — |
| `tests/test_vault_reader.py` | CREATE | — | — | — |
| `tests/test_kardex_vault.py` | CREATE | — | — | — |
| `CHANGELOG.md` | MODIFY | (top of file) | — | — |

---

## 7. Implementation Notes & Constraints

### Patterns to Follow
- Keep the existing reader error contract: `get` → `default`, and `exists` → `False` on errors.
- `logging` module-level calls, as the existing reader does.
- Google-style docstrings and type hints on all new and changed methods.
- Async methods must not hold the event loop: all hvac I/O goes through `asyncio.to_thread`.

### Known Risks / Gotchas
- **Stale secrets after rotation**: the TTL defaults to 300s. `invalidate()`,
  `refresh()` and `reload_current_env()` give manual control.
- **Key-parsing unification** (`set`/`delete` switch from first `/` to last `/`): for
  single-level keys (`dev/KEY`, `KEY`) the result is the same. It only changes nested keys
  (`a/b/KEY`), which were inconsistent with `get()` until now. This must be called out in the CHANGELOG.
- **Mutation leaks**: `list()` must return a copy, and `get()` of a dict-valued secret must
  not let callers mutate the cached document (return shallow copies of dict values).
- **Negative cache hides newly created secrets** until the TTL expires or `set()`
  (write-through) runs. That's acceptable and should be documented.
- **Deadlock**: never call the loader while holding the global cache lock. Only
  the per-key lock is held during I/O.
- **Kardex `_readers` is class-level**: tests must isolate or reset it.
- **Truthiness in `Kardex.get`** (`if val := self._get_external(key)`) is kept as is. It's
  out of scope.

### External Dependencies
None new. `hvac>=2.3.0` is already required, and `pytest-asyncio` is already a dev dependency.

---

## 8. Open Questions

- [ ] Is `VAULT_CACHE_TTL` default = 300s acceptable for production secret rotation? *Owner: Jesus Lara*
- [ ] Should `set_env()` to a different env also invalidate? The proposed answer is no: a different
      path means a different cache key, so it's already correct. *Owner: Jesus Lara*

---

## Worktree Strategy

- **Isolation**: `per-spec`. M1 → M2 → M3 → M4 is a strict dependency chain in the
  same files, so tasks run sequentially in one worktree.
- **Parallelizable**: only the M1 tests could be written alongside M2. The gain isn't
  worth a second worktree.
- **Cross-feature dependencies**: none.

---

## 9. Design Research Cross-Check

Status: skipped (no `codex` seat configured for navconfig).

---

## Revision History

| Version | Date | Author | Change |
|---|---|---|---|
| 0.1 | 2026-09-29 | Jesus Lara / Claude Code | Initial draft from proposal FEAT-001 |
