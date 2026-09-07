# Optional uvloop on Windows

Make uvloop activation lazy and optional while preserving automatic use when
configuration is bootstrapped on supported platforms.

1. Guard Windows before importing uvloop in `navconfig/utils/uvl.py`; use a
   single installation call and retain the missing-dependency fallback.
2. Move automatic activation from package import to `bootstrap()`.
3. Add Windows exclusions to the uvloop extras and tox dependency; refresh
   `uv.lock` and document activation timing in the README.
4. Test deferred imports, Windows skipping, missing dependencies, and automatic
   activation. Run the existing suite and save logs under `artifacts/logs/`.
5. Include Python 3.14: require uvloop >= 0.22.1 and Cython >= 3.1.4, align
   release build requirements, extend tox through 3.14, and validate using
   the installed Python 3.14 interpreter in a separate temporary environment.
6. Remove the redundant `return` in `finally` from `Kardex.__getattr__`, which
   triggers a Python 3.14 SyntaxWarning; preserve existing deserialized return
   values and cover them with regression tests.

Risk: activation now occurs on first configuration access. Existing running
event loops cannot be replaced. Native Windows execution is unavailable;
validate the platform guard using simulated Windows tests.

Validation:

- Python 3.14.3: editable build including Cython extensions succeeded; all 89
  tests passed with SITE_ROOT set to the workspace for the temporary environment.
- Python 3.11.15: all 73 focused uvloop, attribute, and CLI tests passed. The
  full suite was interrupted after 70 passing tests while external-service
  checks delayed completion.
- Real uvloop activation on Python 3.14 passed; Windows/Linux dependency markers
  evaluated correctly; all 40 Python source files compiled with SyntaxWarning
  treated as an error.
- Black and import-order checks passed for the new tests and uvloop helper;
  the lockfile is current and `git diff --check` passed.
- Native Windows execution remains unverified.
