# Plan — run `test_config.py` and `test_kardex_vault.py` in CI

## Problem

`.github/workflows/build.yml` runs the suite with

```
--ignore=tests/test_config.py --ignore=tests/test_kardex_vault.py
```

Both modules import `navconfig.config` at module level. That triggers
`navconfig.bootstrap()`, which resolves the project root and loads
`env/<ENV>/.env`. On a clean clone there is no such file: `env/`, `etc/` and
`settings/` are all git-ignored and nothing equivalent is tracked. So both
modules fail during **collection** with

```
FileExistsError: NavConfig initialization failed: environment assets are missing.
```

and a collection error aborts the whole run — which is why they had to be
ignored outright.

Two further consequences of the current design:

* They only pass on a machine where someone has run `kardex env create`, and
  they assert against *that* configuration (`CONFIG_TEST`,
  `SEND_NOTIFICATIONS`, `SITE_ROOT == <the checkout>`). The suite is not
  reproducible.
* The maintainer's `env/dev/.env` sets `VAULT_ENABLED=true` with a real
  `VAULT_URL`, so bootstrap talks to a live Vault server. That is the entire
  reason the suite took ~302s instead of ~3s.

## Approach

Scaffold a **disposable project** in a temporary directory and point
`SITE_ROOT` at it before any test module imports navconfig. `tests/conftest.py`
is imported first by pytest, so module-level code there runs before collection
of the test modules — which is exactly the window needed.

`navconfig.project.project_root()` honours `SITE_ROOT` ahead of every other
detection strategy, so this needs no production-code change.

### The fixture project

```
<tmp>/
  env/dev/.env          CONFIG_FILE, CONFIG_TEST, SEND_NOTIFICATIONS, ENVIRONMENT
  env/staging/.env      (a second and third environment so the
  env/prod/.env          environment-switching tests have somewhere to go)
  etc/navigator.ini     [info] APP_NAME, [logging] console-only, [temp]
  settings/__init__.py
  settings/settings.py  the three names `navconfig.conf` re-exports
  logs/
```

No `VAULT_*` directives: the Vault tests drive a fake `hvac` client of their
own, and the fixture project must not reach the network.

No `DEBUG`: `test_config` asserts `bool(os.getenv('DEBUG', False)) == DEBUG`,
and `bool("false")` is `True` — defining it either way breaks the assertion.
`conftest` also pops a stray `DEBUG` out of the inherited environment.

### `sys.path`

`navconfig.utils.settings.ensure_settings_priority()` moves the project's
`settings` directory to `sys.path[0]` **when it detects a competing `settings`
package elsewhere on the path**. On a developer machine the checkout itself is
such a competitor (it is `sys.path[0]` under `python -m pytest`, and bootstrap
appends it). With `<tmp>/settings` at position 0, `import settings` resolves to
`<tmp>/settings/settings.py` as a *module*, and `from settings.settings import
...` then fails.

So `conftest` drops any `sys.path` entry that resolves to the checkout root and
inserts the fixture root instead. Nothing needs the checkout on `sys.path`:
`navconfig` is served by the editable install's meta-path finder and `tests/`
is inserted by pytest.

### `os.chdir`

`navconfig/conf.py` does `os.chdir(str(BASE_DIR))` at import. Today that is a
no-op; with the fixture it moves the process into the temporary directory. A
session-scoped autouse fixture restores the original working directory at
teardown, before `TemporaryDirectory` removal — Windows cannot delete a
directory that is the current one.

## Changes

1. `tests/conftest.py` — new: build the fixture project, export `SITE_ROOT`
   and `ENV=dev`, sanitise `sys.path`, scrub inherited `VAULT_*`/`DEBUG`,
   expose `test_project_root`, restore the cwd.
2. `tests/test_config.py` — assert `SITE_ROOT`/`BASE_DIR` against the fixture
   root instead of against the checkout.
3. `.github/workflows/build.yml` — drop both `--ignore` flags and the comment
   explaining them.
4. `CHANGELOG.md` — record it.

## Verification

* full suite locally, timed (expect seconds, not minutes)
* `build.yml` green on all 6 `tests` jobs (3 OS x 2 interpreters)
