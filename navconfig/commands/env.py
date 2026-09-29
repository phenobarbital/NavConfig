"""``kardex env`` -- scaffold and manage NavConfig environments."""
from __future__ import annotations

import argparse
from pathlib import Path

from .common import (
    BASE_ENV_FILE,
    SPLIT_ENV_FILES,
    CommandError,
    env_directory,
    msg,
    read_sample,
    report,
    resolve_root,
    set_env_variable,
    write_file,
)


def _base_env_content(sample: str) -> str:
    """Return the shared ``env/.env`` body, without the ``ENV=`` pin.

    The shared file is used by every environment, so pinning ``ENV`` in it
    would defeat the purpose of the per-environment directories. The
    assignment is commented out rather than dropped, both to document the
    directive and to give ``kardex env new`` a place to write it back.
    """
    body = "\n".join(
        "# ENV=" if line.strip().startswith("ENV=") else line
        for line in sample.splitlines()
    )
    return body + "\n"


def create_environment(
    env: str,
    project_root: Path,
    split: bool = False,
    force: bool = False,
) -> tuple[dict, dict]:
    """Create the default NavConfig project structure.

    Two complementary environment layouts are scaffolded so the project
    works with either resolution strategy:

    * ``env/.env`` -- shared base file, **without** an ``ENV=`` pin.
    * ``env/<env>/.env`` -- environment-specific file pinned to ``ENV=<env>``.

    Args:
        env: Name of the environment to create (``dev``, ``prod``, ...).
        project_root: Directory the structure is created into.
        split: Also create the supplementary ``.env.*`` files NavConfig
            loads alongside the base ``.env``.
        force: Overwrite files that already exist.

    Returns:
        A ``(created, skipped)`` pair of ``{label: path}`` mappings.
    """
    created: dict = {}
    skipped: dict = {}
    sample = read_sample(".env.sample")

    env_root = project_root / "env"
    env_root.mkdir(parents=True, exist_ok=True)

    # Shared env/.env -- common to every environment, no ENV= assignment.
    base_env_file = env_root / BASE_ENV_FILE
    target = created if write_file(
        base_env_file, _base_env_content(sample), force
    ) else skipped
    target["env/.env"] = base_env_file

    # Environment-specific env/<env>/.env -- pinned to ENV=<env>.
    env_path = env_directory(project_root, env)
    env_path.mkdir(parents=True, exist_ok=True)

    env_file = env_path / BASE_ENV_FILE
    target = created if write_file(
        env_file, set_env_variable(sample, "ENV", env), force
    ) else skipped
    target[f"env/{env}/.env"] = env_file

    if split:
        for filename in SPLIT_ENV_FILES:
            path = env_path / filename
            content = read_sample(f"{filename}.sample")
            target = created if write_file(path, content, force) else skipped
            target[f"env/{env}/{filename}"] = path

    # etc/config.ini
    config_file = project_root / "etc" / "config.ini"
    target = created if write_file(
        config_file, read_sample("config.ini.sample"), force
    ) else skipped
    target["etc/config.ini"] = config_file

    # logs/ directory (referenced by the default logging configuration)
    logs_directory = project_root / "logs"
    logs_directory.mkdir(parents=True, exist_ok=True)
    created["logs/"] = logs_directory

    # templates/ directory
    templates_directory = project_root / "templates"
    templates_directory.mkdir(parents=True, exist_ok=True)
    created["templates/"] = templates_directory

    return created, skipped


def new_environment(
    name: str,
    project_root: Path,
    split: bool = False,
    force: bool = False,
) -> tuple[dict, dict]:
    """Create an additional environment from the shared ``env/.env``.

    When no shared ``env/.env`` exists the bundled sample is used instead.

    Args:
        name: Name of the new environment (``prod``, ``staging``, ``qa``).
        project_root: Project root directory.
        split: Also create the supplementary ``.env.*`` files.
        force: Overwrite the environment file when it already exists.

    Returns:
        A ``(created, skipped)`` pair of ``{label: path}`` mappings.
    """
    created: dict = {}
    skipped: dict = {}

    base_env_file = project_root / "env" / BASE_ENV_FILE
    if base_env_file.exists():
        content = base_env_file.read_text(encoding="utf-8")
    else:
        content = read_sample(".env.sample")

    # Re-point the environment token, whatever the base file was pinned to.
    content = set_env_variable(content, "ENV", name)

    env_path = env_directory(project_root, name)
    env_file = env_path / BASE_ENV_FILE
    if env_file.exists() and not force:
        raise CommandError(
            f"Environment '{name}' already exists: {env_file}\n"
            "Re-run with --force to overwrite it."
        )

    write_file(env_file, content, force=True)
    created[f"env/{name}/.env"] = env_file

    if split:
        for filename in SPLIT_ENV_FILES:
            path = env_path / filename
            body = read_sample(f"{filename}.sample")
            target = created if write_file(path, body, force) else skipped
            target[f"env/{name}/{filename}"] = path

    return created, skipped


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``env`` command group."""
    parser = subparsers.add_parser(
        "env",
        help="Create and manage NavConfig environments.",
        description="Create and manage NavConfig environments.",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    create = actions.add_parser(
        "create",
        help="Create the default NavConfig project structure.",
        description=(
            "Create the env/, etc/, logs/ and templates/ directories along "
            "with the base .env and etc/config.ini files."
        ),
    )
    create.add_argument(
        "--env",
        default="dev",
        help="Name of the environment to create (default: dev).",
    )
    create.add_argument(
        "--path",
        default=".",
        help="Project root directory (default: current directory).",
    )
    create.add_argument(
        "--split",
        action="store_true",
        default=False,
        help=(
            "Also create the supplementary .env files NavConfig loads "
            "alongside the base one: "
            f"{', '.join(SPLIT_ENV_FILES)}."
        ),
    )
    create.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite files that already exist.",
    )
    create.set_defaults(func=_run_create)

    new = actions.add_parser(
        "new",
        help="Create an additional environment from the shared env/.env.",
        description="Create an additional environment from the shared env/.env.",
    )
    new.add_argument(
        "name",
        help="Name of the new environment (e.g. prod, staging, qa).",
    )
    new.add_argument(
        "--path",
        default=".",
        help="Project root directory (default: current directory).",
    )
    new.add_argument(
        "--split",
        action="store_true",
        default=False,
        help="Also create the supplementary .env files.",
    )
    new.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Overwrite the environment file when it already exists.",
    )
    new.set_defaults(func=_run_new)


def _run_create(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    created, skipped = create_environment(
        env=args.env,
        project_root=project_root,
        split=args.split,
        force=args.force,
    )
    msg(
        f"NavConfig project structure ready at {project_root} "
        f"(environment: {args.env})"
    )
    report(created, skipped)
    msg("")
    msg(f"Next: edit env/{args.env}/.env, then run your application with "
        f"ENV={args.env}.")
    return 0


def _run_new(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    created, skipped = new_environment(
        name=args.name,
        project_root=project_root,
        split=args.split,
        force=args.force,
    )
    msg(f"Created environment '{args.name}' at {project_root}")
    report(created, skipped)
    return 0
