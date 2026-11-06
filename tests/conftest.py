"""Session-wide scaffolding for the NavConfig test suite.

``tests/test_config.py`` and ``tests/test_kardex_vault.py`` import
``navconfig.config`` at module level, which runs :func:`navconfig.bootstrap`:
it resolves the project root and loads ``env/<ENV>/.env``. The only project
that satisfied them used to be the maintainer's own checkout -- ``env/``,
``etc/`` and ``settings/`` are all git-ignored and nothing equivalent is
tracked -- so on a clean clone, and therefore on every CI runner, both modules
failed during *collection* with::

    FileExistsError: NavConfig initialization failed: environment assets are
    missing.

A collection error aborts the entire run, which is why both files had to be
``--ignore``-d in ``.github/workflows/build.yml``.

This module scaffolds a disposable project in a temporary directory and points
``SITE_ROOT`` at it *before* any test module imports navconfig: pytest imports
``conftest.py`` first, so module-level code here runs inside exactly the window
needed. :func:`navconfig.project.project_root` honours ``SITE_ROOT`` ahead of
every other detection strategy, so no production code has to change.

Two consequences worth knowing:

* The suite no longer depends on -- nor can be polluted by -- whatever
  configuration happens to live in the checkout.
* The fixture project declares no Vault. The Vault-backed tests drive a fake
  ``hvac`` client of their own; bootstrap used to pick up the maintainer's real
  ``VAULT_URL`` and talk to a live server over the network, which is what made
  the suite take ~300s instead of a few seconds.
"""
from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

import pytest

#: Environments the fixture project ships. More than one is required: the
#: environment-switching tests need somewhere to switch *to*.
ENVIRONMENTS: tuple[str, ...] = ("dev", "staging", "prod")

#: Default environment, exported as ``ENV`` so that ``Kardex`` reports a
#: concrete ``current_env`` rather than the empty string.
DEFAULT_ENV: str = "dev"

#: Value used to prove the whole chain resolves: ``env/<env>/.env`` ->
#: ``config.get()`` -> ``settings.settings`` -> ``navconfig.conf``. Keeping it
#: different from the ``CONFIG_TEST`` fallback is deliberate; with the fallback
#: value the assertions would hold even if nothing were loaded at all.
CONFIG_TEST_VALUE: str = "navconfig-test-fixture"

#: Variables that must not leak in from the developer's shell. ``VAULT_*``
#: would send bootstrap to a real server; ``DEBUG`` breaks
#: ``test_config``, which compares ``bool(os.getenv('DEBUG', False))`` against
#: the resolved flag -- and ``bool("false")`` is ``True``.
_SCRUBBED_VARS: tuple[str, ...] = (
    "BASE_DIR",
    "CACHE_BACKEND",
    "CONFIG_CREATE",
    "DEBUG",
    "ENV_TYPE",
    "LAZY_LOAD",
    "PRODUCTION",
    "USE_REDIS",
    "USE_VAULT",
    "VAULT_ENABLED",
    "VAULT_ENV",
    "VAULT_MOUNT_POINT",
    "VAULT_TOKEN",
    "VAULT_URL",
    "VAULT_VERSION",
)

_REPO_ROOT: Path = Path(__file__).resolve().parent.parent

# Held for the lifetime of the module: its finalizer removes the directory
# when the interpreter exits.
_TMPDIR = tempfile.TemporaryDirectory(prefix="navconfig-tests-")

#: Root of the disposable project the whole suite runs against.
PROJECT_ROOT: Path = Path(_TMPDIR.name).resolve()


def _write(path: Path, content: str) -> None:
    """Write ``content`` to ``path``, creating parent directories.

    Args:
        path: File to create.
        content: Text to write; leading indentation is stripped.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip(), encoding="utf-8")


def _env_file(environment: str) -> str:
    """Build the ``.env`` body for one environment.

    ``DEBUG`` is deliberately absent -- see :data:`_SCRUBBED_VARS`.

    Args:
        environment: Environment name (the ``env/<name>/`` directory).

    Returns:
        Contents of ``env/<name>/.env``.
    """
    return f"""
        # Disposable test environment. No secrets, no Vault, no network.
        CONFIG_FILE=etc/navigator.ini
        ENVIRONMENT={environment}
        CONFIG_TEST={CONFIG_TEST_VALUE}
        SEND_NOTIFICATIONS=true
    """


def _build_project(root: Path) -> None:
    """Scaffold a complete, minimal NavConfig project under ``root``.

    Args:
        root: Directory to populate; it becomes ``SITE_ROOT``.
    """
    for environment in ENVIRONMENTS:
        _write(root / "env" / environment / ".env", _env_file(environment))

    # Absolute paths: ``navconfig.logging`` resolves ``logdir`` against the
    # current working directory, which these tests move around.
    logs = root / "logs"
    tmp = root / "tmp"
    logs.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)

    _write(
        root / "etc" / "navigator.ini",
        f"""
        [info]
        APP_NAME = navconfig-tests
        APP_TITLE = NavConfig test fixture

        [logging]
        logdir = {logs}
        loglevel = DEBUG
        logging_echo = false
        logging_disable_other = false
        filehandler_enabled = false
        logstash_enabled = false
        mailer_enabled = false
        handlers = console

        [temp]
        temp_path = {tmp}
        """,
    )

    _write(
        root / "settings" / "__init__.py",
        '"""Settings package of the disposable test project."""\n',
    )
    _write(
        root / "settings" / "settings.py",
        '''
        """Global settings of the disposable test project.

        ``navconfig.conf`` re-exports everything defined here, and
        ``tests/test_config.py`` asserts that the two agree.
        """
        import sys

        from navconfig import DEBUG, config

        LOCAL_DEVELOPMENT = DEBUG is True and sys.argv[0] == "run.py"
        SEND_NOTIFICATIONS = config.getboolean("SEND_NOTIFICATIONS", fallback=True)
        CONFIG_TEST = config.get("CONFIG_TEST", fallback="NAVCONFIG")
        ''',
    )


def _isolate_sys_path(root: Path) -> None:
    """Make ``root`` the project on ``sys.path``, not the checkout.

    ``navconfig.utils.settings.ensure_settings_priority`` moves the project's
    ``settings`` directory to ``sys.path[0]`` whenever it detects a competing
    ``settings`` package elsewhere on the path. On a developer machine the
    checkout is such a competitor, and with ``<fixture>/settings`` at position
    zero ``import settings`` resolves to ``<fixture>/settings/settings.py`` as a
    *module*, so ``from settings.settings import ...`` fails. Dropping the
    checkout removes the competition.

    Nothing needs the checkout on ``sys.path``: ``navconfig`` is served by the
    editable install's meta-path finder, and pytest inserts ``tests/`` itself.
    The checkout is only dropped when it really does carry a ``settings``
    package, so on a clean clone -- CI -- this leaves ``sys.path`` untouched.

    Args:
        root: Root of the fixture project.
    """
    if (_REPO_ROOT / "settings" / "__init__.py").exists():
        for entry in list(sys.path):
            with contextlib.suppress(OSError, ValueError):
                if Path(entry or ".").resolve() == _REPO_ROOT:
                    sys.path.remove(entry)
    sys.path.insert(0, str(root))


_build_project(PROJECT_ROOT)
_isolate_sys_path(PROJECT_ROOT)

for _name in _SCRUBBED_VARS:
    os.environ.pop(_name, None)
os.environ["SITE_ROOT"] = str(PROJECT_ROOT)
os.environ["ENV"] = DEFAULT_ENV


@pytest.fixture(scope="session")
def test_project_root() -> Path:
    """Root of the disposable project the suite runs against.

    Returns:
        The directory exported as ``SITE_ROOT``.
    """
    return PROJECT_ROOT


@pytest.fixture(scope="session", autouse=True)
def _restore_cwd():
    """Put the working directory back when the session ends.

    ``navconfig/conf.py`` runs ``os.chdir(str(BASE_DIR))`` at import time, which
    leaves the process inside the temporary project. Windows refuses to remove a
    directory that is the current one, so the interpreter has to step out before
    :class:`tempfile.TemporaryDirectory` finalizes.
    """
    cwd = os.getcwd()
    yield
    with contextlib.suppress(OSError):
        os.chdir(cwd)
