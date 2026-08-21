# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.0.0] - 2026-08-21

Breaking release: the `kardex` CLI is now organised in sub-commands and the
`navconfig` package builds its configuration lazily.

### Added
* Sub-command groups for `kardex`, replacing the flat command layout:
  * `kardex env create` -- scaffold `env/`, `etc/config.ini`, `logs/` and
    `templates/` (what `kardex create` used to do).
  * `kardex env create --split` -- also create the supplementary
    `.env.resources`, `.env.databases`, `.env.api`, `.env.cache` and
    `.env.local` files NavConfig loads alongside the base `.env`.
  * `kardex env new <name>` -- add an environment from the shared `env/.env`
    (replaces `kardex new-env`).
  * `kardex vault create` -- write the HashiCorp Vault directives into
    `env/<env>/.env`, creating the file when it does not exist yet.
  * `kardex vault migrate` -- push the variables of an environment into
    Vault, with `--dry-run`, `--include-extra` and `--keep-existing`.
  * `kardex vault save VARIABLE:VALUE` -- store one or more variables in
    Vault.
  * `kardex log enable [--logstash]` -- write the `[logging]` section of
    `etc/config.ini`, optionally enabling the Logstash handler.
* `kardex --version`, and a `--force` flag on the scaffolding commands.
* `navconfig.bootstrap()`, the explicit entry point to the initialization
  that used to happen at import time.
* Bundled samples for the split `.env` layout and for the Vault block.

### Changed
* **Initialization order.** `navconfig/__init__.py` no longer instantiates
  `Kardex` while the package is being imported; `config`, `BASE_DIR`,
  `DEBUG` and the other package-level names are resolved on first access
  (PEP 562). Importing `navconfig.cli` therefore no longer requires an
  `env/` directory -- the bug that made `kardex create` fail on precisely
  the fresh projects it was supposed to bootstrap. Code that relied on
  `import navconfig` alone to populate `os.environ` must now call
  `navconfig.bootstrap()` (or touch any exported name) explicitly.
* `kardex vault create` writes `VAULT_URL`, `VAULT_MOUNT_POINT` and
  `VAULT_VERSION` -- the directives NavConfig actually reads. The previous
  `new-env --vault` block advertised `VAULT_ADDR`, `VAULT_ROLE_ID`,
  `VAULT_SECRET_ID`, `VAULT_SECRET_PATH` and `VAULT_NAMESPACE`, none of
  which are consulted by the loader.
* The Vault block is delimited by `# --- navconfig:vault ---` markers, so
  `kardex vault create --force` rewrites it without duplicating directives.
* `kardex log enable` edits `etc/config.ini` line by line, preserving the
  comments that document each option.
* The "environment is missing" errors now point at `kardex env create`.

### Removed
* `kardex create` and `kardex new-env`. Use `kardex env create` and
  `kardex env new` instead. There is no compatibility shim.

## [2.3.0] - 2026-08-07
### Added
* Official support for Python 3.13 and 3.14: both are now built in the release
  wheel matrix (`cp313-cp313`, `cp314-cp314`) and advertised via trove classifiers.
* `VAULT_ENV` to override the vault path segment independently of `ENV`.

### Changed
* Relaxed `hvac` from the exact pin `==2.3.0` to `>=2.3.0`, matching the
  constraint already used by the `all`, `default` and `hvac` extras.

### Fixed
* The `build` job no longer runs a redundant Python matrix. The manylinux action
  builds every interpreter listed in `python-versions` inside its own container,
  so the matrix was rebuilding the identical set of wheels once per version.

### Removed
* Dropped the stale `Programming Language :: Python :: 3.9` classifier, which
  contradicted `requires-python = ">=3.10.1"`.

## [1.0.0] - 2022-10-18
* Added python-datamodel as dependency for build Dataclasses.
* replaced rapidjson with orjson.
* fix some issues in publish-to-pypi GH.
* Adding support for in-memory config dictionary based on YAML or TOML
* Config Readers from Memcache and Redis
* Support for replacing INI files with TOML or YAML configuration files.

## [0.9.1] - 2021-10-20
* First stable version with support to Python +3.8
* Fixing issues over pyproject.toml
