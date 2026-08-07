# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
