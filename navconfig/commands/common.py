"""Shared helpers for the ``kardex`` sub-commands.

Nothing in this module may touch :data:`navconfig.config`: the CLI has to
run *before* a project owns an ``env/`` directory, which is exactly the
situation where building the global configuration fails.
"""
from __future__ import annotations

import sys
from pathlib import Path

from ..samples import get_sample_path

#: Base file of an environment, always loaded first.
BASE_ENV_FILE = ".env"

#: Delimiters of the Vault block ``kardex vault create`` manages inside a
#: ``.env`` file. Keeping them lets the command rewrite its own block
#: without touching anything the user added around it.
VAULT_BLOCK_START = "# --- navconfig:vault ---"
VAULT_BLOCK_END = "# --- navconfig:vault:end ---"

#: Supplementary files created by ``kardex env create --split``, in the
#: order NavConfig loads them (``.env.local`` last, so it always wins).
SPLIT_ENV_FILES = (
    ".env.resources",
    ".env.databases",
    ".env.api",
    ".env.cache",
    ".env.local",
)


class CommandError(Exception):
    """Raised when a sub-command cannot complete its work."""


def msg(text: str = "") -> None:
    """Print an informational message to stdout."""
    sys.stdout.write(f"{text}\n")


def warn(text: str) -> None:
    """Print a warning to stderr."""
    sys.stderr.write(f"warning: {text}\n")


def read_sample(name: str) -> str:
    """Read a bundled sample file and return its text."""
    return get_sample_path(name).read_text(encoding="utf-8")


def resolve_root(path: str) -> Path:
    """Return the absolute project root for a ``--path`` argument."""
    return Path(path).expanduser().resolve()


def env_directory(project_root: Path, env: str) -> Path:
    """Return the directory holding the files of a given environment."""
    return project_root / "env" / env


def write_file(path: Path, content: str, force: bool = False) -> bool:
    """Write *content* into *path*, creating parent directories.

    Args:
        path: Destination file.
        content: Text to write.
        force: Overwrite the file when it already exists.

    Returns:
        ``True`` when the file was written, ``False`` when it already
        existed and *force* was not set.
    """
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def report(created: dict, skipped: dict = None) -> None:
    """Print the files/directories a sub-command produced."""
    for label, path in created.items():
        msg(f"  created  {label}: {path}")
    for label, path in (skipped or {}).items():
        msg(f"  skipped  {label}: {path} (already exists)")


def set_env_variable(content: str, key: str, value: str) -> str:
    """Return *content* with ``key`` set to ``value``.

    An existing (possibly commented-out) assignment is replaced in place so
    the surrounding comments survive; otherwise the assignment is appended.
    """
    lines = content.splitlines()
    replaced = False
    for index, line in enumerate(lines):
        stripped = line.lstrip("#").strip()
        if stripped.split("=", 1)[0].strip() == key:
            lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"
