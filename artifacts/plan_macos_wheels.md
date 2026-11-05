# macOS (Apple Silicon) wheels in release.yml

## Goal

`release.yml` must build and publish `macosx_*_arm64` wheels for CPython
3.10-3.14 alongside the existing manylinux2014 x86_64 and Windows x64 wheels.

## Findings that drove the plan

1. **The publish step would have dropped macOS wheels silently.** `twine upload`
   listed explicit globs (`dist/*-manylinux*.whl dist/*-win_amd64.whl
   dist/*.tar.gz`); a `*-macosx_11_0_arm64.whl` matches none of them, so it
   would have been downloaded, moved into `dist/`, listed -- and never
   uploaded, with a green build. Fixed by uploading `dist/*` after the
   completeness gate, which is what that gate is for.
2. **No source change is needed for macOS.** The extensions declare no
   `libraries`/`include_dirs`, the only C++ dependency is
   `from libcpp cimport bool` (`navconfig/logging/logger.pyx`), and
   `navconfig/utils/uvl.py` already guards uvloop by `sys.platform`. The
   sdist ships `*.pyx`/`*.pxd`, so it compiles on macOS too.
3. **`macos-13` is retired** (no runner since 2025-12-04) and `macos-latest`
   now resolves to macOS 26. Pin `macos-15`: arm64, stable, Intel-free.
4. **`actions/python-versions` has no darwin-arm64 build before 3.10.11.**
   Requesting `"3.10"` resolves to the newest patch, which does have arm64, so
   `setup-python` is safe here -- but the constraint is recorded in the
   workflow so a future pin to an exact old patch does not break silently.
5. **`CYTHON_COMPILING_IN_PYPY=1`** was defined for `navconfig.exceptions`.
   That macro tells Cython-generated C it runs under PyPy and enables
   `#if CYTHON_COMPILING_IN_PYPY` branches on CPython. It is preprocessor-only
   so it compiled everywhere, but it is a latent bug, not an optimization.
6. **There was no CI that compiles the project.** Only `codeql-analysis.yml`,
   `pages.yml` and `release.yml` existed, so the first macOS compile would
   have happened during a real release, after the GitHub release was created.

## Changes

- `.github/workflows/release.yml`
  - new `build-macos` job: `macos-15`, `architecture: arm64`, matrix
    3.10-3.14, `MACOSX_DEPLOYMENT_TARGET=11.0`, `uv build --wheel`, plus a
    `delocate-wheel --require-archs arm64` architecture gate.
  - `deploy`: `needs` includes `build-macos`; `check_dist` exports
    `HAS_MACOS_WHEELS`; the completeness gate requires it; `twine upload dist/*`.
  - `test-install`: adds `macos-15` to the OS matrix and drops
    `continue-on-error`, so a broken published wheel fails the run.
  - `if-no-files-found: error` on every upload step.
- `.github/workflows/build.yml` (new): compile + test on Linux/Windows/macOS
  for every push and PR, so platform breakage surfaces before a release.
- `setup.py`: drop `CYTHON_COMPILING_IN_PYPY`; select `-O2` vs `/O2` per
  compiler instead of relying on MSVC accepting `-O2`.
- `pyproject.toml`: real OS classifiers instead of only `OS Independent`.

## Out of scope

- Linux aarch64 and Windows arm64 wheels.
- macOS x86_64 wheels (`macos-15-intel`); Intel users fall back to the sdist.
- Migrating all three platforms to `cibuildwheel` -- recommended follow-up,
  but it rewrites the working Linux/Windows jobs and this pipeline can only
  be validated by cutting a real release.

## Verification

- `python -c "import yaml; yaml.safe_load(...)"` on both workflows.
- `python setup.py build_ext --inplace` to prove the extensions still compile
  without the PyPy macro and with the new compiler-arg selection.
- `pytest` (full suite).
- Native Windows/macOS compilation can only be verified on GitHub Actions.
