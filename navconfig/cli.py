"""Command line tools for managing NavConfig projects."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .samples import get_sample_path

# ---------------------------------------------------------------------------
# Vault-related variables appended when --vault is used with new-env
# ---------------------------------------------------------------------------
VAULT_ENV_BLOCK = """\

# -- HashiCorp Vault --
VAULT_ENABLED=true
VAULT_ADDR=https://vault.example.com:8200
VAULT_TOKEN=
VAULT_ROLE_ID=
VAULT_SECRET_ID=
VAULT_MOUNT_POINT=secret
VAULT_SECRET_PATH=apps/{app_name}
VAULT_NAMESPACE=
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_sample(name: str) -> str:
    """Read a bundled sample file and return its text."""
    return get_sample_path(name).read_text(encoding="utf-8")


def _msg(text: str) -> None:
    """Print an informational message to stdout."""
    sys.stdout.write(text + "\n")


# ---------------------------------------------------------------------------
# Subcommand: create
# ---------------------------------------------------------------------------

def create_project_structure(env_name: str, project_root: Path) -> dict[str, Path]:
    """Create the default NavConfig project structure from sample files."""
    # env/<env_name>/.env
    env_directory = project_root / "env" / env_name
    env_directory.mkdir(parents=True, exist_ok=True)

    env_file = env_directory / ".env"
    if not env_file.exists():
        content = _read_sample(".env.sample")
        # Replace the placeholder environment name
        content = content.replace("ENV=dev", f"ENV={env_name}")
        env_file.write_text(content, encoding="utf-8")

    # etc/config.ini
    etc_directory = project_root / "etc"
    etc_directory.mkdir(parents=True, exist_ok=True)

    config_file = etc_directory / "config.ini"
    if not config_file.exists():
        content = _read_sample("config.ini.sample")
        config_file.write_text(content, encoding="utf-8")

    # logs/ directory (referenced by default logging config)
    logs_directory = project_root / "logs"
    logs_directory.mkdir(parents=True, exist_ok=True)

    return {
        "env_directory": env_directory,
        "env_file": env_file,
        "etc_directory": etc_directory,
        "config_file": config_file,
    }


# ---------------------------------------------------------------------------
# Subcommand: new-env
# ---------------------------------------------------------------------------

def create_new_environment(
    name: str,
    project_root: Path,
    vault: bool = False,
) -> dict[str, Path]:
    """Create a new environment directory by copying the base env/.env.

    If no base env/.env exists the bundled sample is used instead.
    When *vault* is ``True`` the HashiCorp Vault connection variables
    are appended to the new file.
    """
    base_env_file = project_root / "env" / ".env"
    if base_env_file.exists():
        base_content = base_env_file.read_text(encoding="utf-8")
    else:
        # Fall back to the bundled sample
        base_content = _read_sample(".env.sample")

    # Replace the environment token in the content
    # Handle both quoted and unquoted forms
    for old in ("ENV=dev", "ENV=staging", "ENV=prod", "ENV=production"):
        base_content = base_content.replace(old, f"ENV={name}")

    target_dir = project_root / "env" / name
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / ".env"
    if target_file.exists():
        _msg(f"Environment file already exists: {target_file}")
        _msg("Use --force to overwrite (not implemented yet).")
        sys.exit(1)

    if vault:
        app_name = name  # sensible default for the vault path
        base_content += VAULT_ENV_BLOCK.format(app_name=app_name)

    target_file.write_text(base_content, encoding="utf-8")

    return {
        "env_directory": target_dir,
        "env_file": target_file,
    }


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kardex",
        description="Utilities for bootstrapping and managing NavConfig projects.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- create ---------------------------------------------------------------
    create_parser = subparsers.add_parser(
        "create",
        help="Create the default NavConfig environment structure.",
    )
    create_parser.add_argument(
        "--env",
        default="dev",
        help="Name of the environment to create (default: dev).",
    )
    create_parser.add_argument(
        "--path",
        default=".",
        help="Project directory where the structure should be created.",
    )

    # -- new-env --------------------------------------------------------------
    newenv_parser = subparsers.add_parser(
        "new-env",
        help="Create a new environment from the base env/.env file.",
    )
    newenv_parser.add_argument(
        "name",
        help="Name of the new environment (e.g. prod, staging, qa).",
    )
    newenv_parser.add_argument(
        "--path",
        default=".",
        help="Project root directory (default: current directory).",
    )
    newenv_parser.add_argument(
        "--vault",
        action="store_true",
        default=False,
        help="Include HashiCorp Vault connection variables in the new .env.",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry point for the kardex CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "create":
        project_root = Path(args.path).resolve()
        created = create_project_structure(args.env, project_root)
        _msg(f"Created NavConfig project structure at {project_root} (environment: {args.env})")
        for label, path in created.items():
            _msg(f"  {label} -> {path}")
        return 0

    if args.command == "new-env":
        project_root = Path(args.path).resolve()
        created = create_new_environment(
            name=args.name,
            project_root=project_root,
            vault=args.vault,
        )
        vault_note = " (with Vault variables)" if args.vault else ""
        _msg(f"Created environment '{args.name}'{vault_note} at {created['env_file']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
