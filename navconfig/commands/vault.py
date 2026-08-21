"""``kardex vault`` -- bootstrap and populate a HashiCorp Vault backend."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .common import (
    BASE_ENV_FILE,
    VAULT_BLOCK_END,
    VAULT_BLOCK_START,
    CommandError,
    env_directory,
    msg,
    read_sample,
    report,
    resolve_root,
    set_env_variable,
    warn,
    write_file,
)

#: Directives owned by the Vault integration itself. They configure *how* to
#: reach Vault, so pushing them into Vault would be circular: NavConfig has
#: to read them from the .env file before it can open a connection.
VAULT_OWN_VARIABLES = (
    "VAULT_ENABLED",
    "VAULT_URL",
    "VAULT_TOKEN",
    "VAULT_MOUNT_POINT",
    "VAULT_VERSION",
    "VAULT_ENV",
    "VAULT_NAMESPACE",
)

#: Directives NavConfig needs *before* any external source is reachable:
#: they select the environment, the INI file and the project layout. Storing
#: them in Vault would be circular, so ``kardex vault migrate`` leaves them
#: in the .env file unless ``--include-bootstrap`` is given.
BOOTSTRAP_VARIABLES = (
    "ENV",
    "ENV_TYPE",
    "SITE_ROOT",
    "BASE_DIR",
    "CONFIG_FILE",
    "LAZY_LOAD",
    "AUTO_DISCOVERY",
    "CONFIG_CREATE",
    "PROJECT_NAME",
    "PROJECT_PATH",
    "PROJECT_FILE",
    "NAVCONFIG_FILE_OVERRIDE_ENABLED",
)


def _mask(value: Any) -> str:
    """Return a redacted representation of a secret value."""
    text = str(value)
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * (len(text) - 4)}{text[-2:]}"


def is_vault_variable(key: str) -> bool:
    """Return ``True`` when *key* configures the Vault connection itself."""
    return key in VAULT_OWN_VARIABLES or key.startswith("VAULT_")


# ---------------------------------------------------------------------------
# vault create
# ---------------------------------------------------------------------------

def _strip_vault_block(content: str) -> tuple[str, bool]:
    """Remove the managed Vault block from *content*.

    Returns the remaining text and whether an *unmanaged* block (Vault
    directives written by hand, without the delimiters) was found instead.
    """
    lines = content.splitlines()
    kept, inside, managed = [], False, False
    for line in lines:
        if line.startswith(VAULT_BLOCK_START):
            inside = managed = True
            continue
        if inside:
            if line.startswith(VAULT_BLOCK_END):
                inside = False
            continue
        kept.append(line)

    if managed:
        return "\n".join(kept).rstrip() + "\n", False

    # No delimiters: drop the bare VAULT_* assignments and report it, so the
    # caller can warn that surrounding comments were left untouched.
    kept = [
        line for line in lines
        if not line.split("=", 1)[0].strip().startswith("VAULT_")
    ]
    return "\n".join(kept).rstrip() + "\n", True


def create_vault_env(
    env: str,
    project_root: Path,
    url: str = None,
    token: str = None,
    mount_point: str = None,
    version: int = None,
    vault_env: str = None,
    force: bool = False,
) -> tuple[dict, dict]:
    """Write the Vault directives into ``env/<env>/.env``.

    When the environment file does not exist yet it is created from the
    base sample, so ``kardex vault create`` also works as a one-step
    bootstrap for a Vault-backed project. The block is delimited by
    ``# --- navconfig:vault ---`` markers so it can be rewritten later
    without disturbing the rest of the file.

    Args:
        env: Environment whose ``.env`` file is configured.
        project_root: Project root directory.
        url: Address of the Vault server.
        token: Token used to authenticate.
        mount_point: KV mount point holding the application secrets.
        version: KV engine version (1 or 2).
        vault_env: Path segment to read secrets from, when it must differ
            from *env*.
        force: Rewrite the Vault block even if one is already present.

    Returns:
        A ``(created, skipped)`` pair of ``{label: path}`` mappings.
    """
    created: dict = {}
    skipped: dict = {}

    env_path = env_directory(project_root, env)
    env_file = env_path / BASE_ENV_FILE

    if env_file.exists():
        content = env_file.read_text(encoding="utf-8")
    else:
        content = set_env_variable(read_sample(".env.sample"), "ENV", env)
        created[f"env/{env}/.env"] = env_file

    has_block = VAULT_BLOCK_START in content or "VAULT_ENABLED" in content
    if has_block and not force:
        skipped[f"env/{env}/.env (Vault block)"] = env_file
    else:
        if has_block:
            content, unmanaged = _strip_vault_block(content)
            if unmanaged:
                warn(
                    "replaced hand-written VAULT_* directives; review "
                    f"{env_file} for leftover comments."
                )
        content = content.rstrip() + "\n\n" + read_sample(".env.vault.sample")
        if f"env/{env}/.env" not in created:
            created[f"env/{env}/.env (Vault block)"] = env_file

    overrides = {
        "VAULT_URL": url,
        "VAULT_TOKEN": token,
        "VAULT_MOUNT_POINT": mount_point,
        "VAULT_VERSION": str(version) if version is not None else None,
        "VAULT_ENV": vault_env,
    }
    for key, value in overrides.items():
        if value is not None:
            content = set_env_variable(content, key, value)

    env_path.mkdir(parents=True, exist_ok=True)
    write_file(env_file, content, force=True)

    return created, skipped


# ---------------------------------------------------------------------------
# Vault connection
# ---------------------------------------------------------------------------

class VaultWriter:
    """Minimal Vault KV writer used by the ``kardex vault`` sub-commands.

    ``navconfig.readers.vault.VaultReader`` performs a read-modify-write per
    key, which is both slow and racy when migrating a whole ``.env`` file.
    This writer merges every key in memory and issues a single write.
    """

    def __init__(self, settings: dict) -> None:
        try:
            import hvac  # pylint: disable=import-outside-toplevel
        except ModuleNotFoundError as ex:  # pragma: no cover - dependency
            raise CommandError(
                "HashiCorp Vault support requires the 'hvac' package: "
                "pip install navconfig[hvac]"
            ) from ex

        self._hvac = hvac
        self.url: str = settings["url"]
        self.mount_point: str = settings["mount_point"]
        self.version: int = settings["version"]
        self.path: str = settings["path"]

        if not settings.get("token"):
            raise CommandError(
                "VAULT_TOKEN is not set. Provide it with --token, or add it "
                "to the environment .env file (kardex vault create)."
            )

        try:
            self.client = hvac.Client(url=self.url, token=settings["token"])
            authenticated = self.client.is_authenticated()
        except Exception as ex:
            raise CommandError(f"Unable to reach Vault at {self.url}: {ex}") from ex

        if not authenticated:
            raise CommandError(
                f"Vault rejected the token used for {self.url}. "
                "Check VAULT_TOKEN and its policies."
            )

    def read(self) -> dict:
        """Return the secrets currently stored at the configured path."""
        try:
            if self.version == 1:
                response = self.client.secrets.kv.v1.read_secret(
                    path=self.path, mount_point=self.mount_point
                )
                return dict(response["data"])
            response = self.client.secrets.kv.v2.read_secret_version(
                path=self.path, mount_point=self.mount_point
            )
            return dict(response["data"]["data"])
        except self._hvac.exceptions.InvalidPath:
            # The path simply does not hold a secret yet.
            return {}
        except Exception as ex:
            raise CommandError(
                f"Unable to read '{self.mount_point}/{self.path}': {ex}"
            ) from ex

    def write(self, data: dict) -> None:
        """Replace the secret at the configured path with *data*."""
        try:
            if self.version == 1:
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=self.path, secret=data, mount_point=self.mount_point
                )
            else:
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=self.path, secret=data, mount_point=self.mount_point
                )
        except Exception as ex:
            hint = ""
            if "no handler for route" in str(ex):
                hint = (
                    f"\nThe KV engine does not seem to be mounted at "
                    f"'{self.mount_point}'. Enable it with: vault secrets "
                    f"enable -path={self.mount_point} -version={self.version} kv"
                )
            raise CommandError(
                f"Unable to write to '{self.mount_point}/{self.path}': {ex}{hint}"
            ) from ex


def load_env_values(path: Path) -> dict:
    """Return the variables declared in a ``.env`` file, without side effects."""
    from dotenv import dotenv_values  # pylint: disable=import-outside-toplevel

    if not path.exists():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v is not None}


def resolve_settings(args: argparse.Namespace, project_root: Path) -> dict:
    """Resolve the Vault connection settings for a sub-command.

    Precedence is: explicit command-line flags, then the environment's
    ``.env`` file, then the process environment.
    """
    env_file = env_directory(project_root, args.env) / BASE_ENV_FILE
    file_values = load_env_values(env_file)

    def pick(flag: Any, key: str, default: Any = None) -> Any:
        if flag is not None:
            return flag
        return file_values.get(key, os.getenv(key, default))

    version = pick(args.version, "VAULT_VERSION", "2")
    try:
        version = int(version)
    except (TypeError, ValueError) as ex:
        raise CommandError(f"VAULT_VERSION must be 1 or 2, got {version!r}") from ex
    if version not in (1, 2):
        raise CommandError(f"VAULT_VERSION must be 1 or 2, got {version!r}")

    path = (
        getattr(args, "vault_path", None)
        or file_values.get("VAULT_ENV")
        or os.getenv("VAULT_ENV")
        or args.env
    )

    return {
        "url": pick(args.url, "VAULT_URL", "http://localhost:8200"),
        "token": pick(args.token, "VAULT_TOKEN"),
        "mount_point": pick(args.mount_point, "VAULT_MOUNT_POINT", "navigator"),
        "version": version,
        "path": path,
        "env_file": env_file,
    }


def _confirm(question: str, assume_yes: bool) -> bool:
    """Ask for confirmation before writing to a remote Vault server."""
    if assume_yes:
        return True
    try:
        answer = input(f"{question} [y/N]: ")
    except (EOFError, KeyboardInterrupt):
        msg("")
        return False
    return answer.strip().lower() in ("y", "yes")


# ---------------------------------------------------------------------------
# vault migrate
# ---------------------------------------------------------------------------

def collect_migratable(
    project_root: Path,
    env: str,
    source: Path = None,
    include_extra: bool = False,
    include_bootstrap: bool = False,
) -> tuple[dict, dict]:
    """Split an environment into the variables that belong in Vault or not.

    Args:
        project_root: Project root directory.
        env: Environment to read.
        source: Read this file instead of ``env/<env>/.env``.
        include_extra: Also read the supplementary ``env/<env>/.env.*`` files.
        include_bootstrap: Migrate the NavConfig bootstrap directives too.

    Returns:
        A ``(migratable, excluded)`` pair, where *excluded* maps each
        left-behind variable to the reason it was left behind.
    """
    env_path = env_directory(project_root, env)
    if source is not None:
        files = [source]
    else:
        files = [env_path / BASE_ENV_FILE]
        if include_extra:
            files.extend(
                sorted(
                    path for path in env_path.glob(".env.*")
                    if path.is_file()
                )
            )

    values: dict = {}
    for path in files:
        if not path.exists():
            raise CommandError(f"Environment file not found: {path}")
        values.update(load_env_values(path))

    migratable: dict = {}
    excluded: dict = {}
    for key, value in values.items():
        if is_vault_variable(key):
            excluded[key] = "configures the Vault connection"
        elif not include_bootstrap and key in BOOTSTRAP_VARIABLES:
            excluded[key] = "NavConfig bootstrap directive"
        else:
            migratable[key] = value

    return migratable, excluded


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _add_connection_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env",
        default=os.getenv("ENV") or "dev",
        help="Environment to operate on (default: $ENV, or dev).",
    )
    parser.add_argument(
        "--path",
        default=".",
        help="Project root directory (default: current directory).",
    )
    parser.add_argument("--url", default=None, help="Vault server address.")
    parser.add_argument("--token", default=None, help="Vault token.")
    parser.add_argument(
        "--mount-point",
        default=None,
        help="KV mount point holding the application secrets.",
    )
    parser.add_argument(
        "--version",
        default=None,
        type=int,
        choices=(1, 2),
        help="KV engine version (default: 2).",
    )
    parser.add_argument(
        "--vault-path",
        default=None,
        help=(
            "Secret path under the mount point. Defaults to VAULT_ENV when "
            "set, otherwise to the environment name."
        ),
    )


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``vault`` command group."""
    parser = subparsers.add_parser(
        "vault",
        help="Configure and populate a HashiCorp Vault backend.",
        description="Configure and populate a HashiCorp Vault backend.",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    # -- vault create ------------------------------------------------------
    create = actions.add_parser(
        "create",
        help="Write the HashiCorp Vault directives into env/<env>/.env.",
        description=(
            "Write the HashiCorp Vault directives into env/<env>/.env, "
            "creating the file from the bundled sample when missing."
        ),
    )
    _add_connection_flags(create)
    create.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Rewrite the Vault block even if one is already present.",
    )
    create.set_defaults(func=_run_create)

    # -- vault migrate -----------------------------------------------------
    migrate = actions.add_parser(
        "migrate",
        help="Push the variables of a .env file into HashiCorp Vault.",
        description=(
            "Push the variables of an environment into HashiCorp Vault. The "
            "VAULT_* directives are never migrated: NavConfig reads them "
            "from the .env file to open the connection."
        ),
    )
    _add_connection_flags(migrate)
    migrate.add_argument(
        "--file",
        default=None,
        help="Migrate this file instead of env/<env>/.env.",
    )
    migrate.add_argument(
        "--include-extra",
        action="store_true",
        default=False,
        help="Also migrate the supplementary env/<env>/.env.* files.",
    )
    migrate.add_argument(
        "--include-bootstrap",
        action="store_true",
        default=False,
        help=(
            "Also migrate the NavConfig bootstrap directives "
            f"({', '.join(BOOTSTRAP_VARIABLES[:3])}, ...), which are "
            "normally kept in the .env file."
        ),
    )
    migrate.add_argument(
        "--keep-existing",
        action="store_true",
        default=False,
        help="Do not overwrite keys already stored in Vault.",
    )
    migrate.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be written without contacting Vault.",
    )
    migrate.add_argument(
        "-y", "--yes",
        action="store_true",
        default=False,
        help="Do not ask for confirmation before writing.",
    )
    migrate.set_defaults(func=_run_migrate)

    # -- vault save --------------------------------------------------------
    save = actions.add_parser(
        "save",
        help="Store one or more variables in HashiCorp Vault.",
        description=(
            "Store one or more VARIABLE:VALUE pairs in HashiCorp Vault. "
            "Only the first colon separates the name from the value, so "
            "values may contain colons themselves."
        ),
    )
    save.add_argument(
        "pairs",
        nargs="+",
        metavar="VARIABLE:VALUE",
        help="Variable and value to store, separated by a colon.",
    )
    _add_connection_flags(save)
    save.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show what would be written without contacting Vault.",
    )
    save.set_defaults(func=_run_save)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _run_create(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    created, skipped = create_vault_env(
        env=args.env,
        project_root=project_root,
        url=args.url,
        token=args.token,
        mount_point=args.mount_point,
        version=args.version,
        vault_env=args.vault_path,
        force=args.force,
    )
    updated = [
        name for name, value in (
            ("VAULT_URL", args.url),
            ("VAULT_TOKEN", args.token),
            ("VAULT_MOUNT_POINT", args.mount_point),
            ("VAULT_VERSION", args.version),
            ("VAULT_ENV", args.vault_path),
        ) if value is not None
    ]

    msg(f"HashiCorp Vault configuration ready for environment '{args.env}'")
    report(created, skipped)
    if updated:
        msg(f"  updated  {', '.join(updated)}")
    if skipped:
        msg("")
        msg("Re-run with --force to rewrite the whole Vault block.")
    if not args.token:
        msg("")
        msg("Remember to set VAULT_TOKEN before starting the application.")
    return 0


def _report_excluded(excluded: dict) -> None:
    """List the variables deliberately left in the .env file."""
    if not excluded:
        return
    msg("")
    msg(f"Left in the .env file ({len(excluded)}):")
    for key, reason in excluded.items():
        msg(f"  {key} -- {reason}")


def _run_migrate(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    source = Path(args.file).expanduser().resolve() if args.file else None

    values, excluded = collect_migratable(
        project_root=project_root,
        env=args.env,
        source=source,
        include_extra=args.include_extra,
        include_bootstrap=args.include_bootstrap,
    )
    if not values:
        msg("Nothing to migrate: every variable stays in the .env file.")
        _report_excluded(excluded)
        return 0

    settings = resolve_settings(args, project_root)
    destination = f"{settings['mount_point']}/{settings['path']}"

    msg(f"Migrating {len(values)} variable(s) to {settings['url']} -> {destination}")
    for key, value in values.items():
        msg(f"  {key} = {_mask(value)}")
    _report_excluded(excluded)

    if args.dry_run:
        msg("")
        msg("Dry run: nothing was written to Vault.")
        return 0

    if not _confirm(f"Write these variables to {destination}?", args.yes):
        msg("Aborted: nothing was written to Vault.")
        return 1

    writer = VaultWriter(settings)
    existing = writer.read()

    payload = dict(existing)
    written, kept = [], []
    for key, value in values.items():
        if args.keep_existing and key in existing:
            kept.append(key)
            continue
        payload[key] = value
        written.append(key)

    if not written:
        msg("Every variable is already present in Vault; nothing written.")
        return 0

    writer.write(payload)

    msg("")
    msg(f"Wrote {len(written)} variable(s) to {destination}.")
    if kept:
        msg(f"Kept {len(kept)} existing value(s): {', '.join(kept)}")
    msg(
        "Remove the migrated values from the .env file once you have "
        "verified the application reads them from Vault."
    )
    return 0


def _parse_pair(pair: str) -> tuple[str, str]:
    """Split a ``VARIABLE:VALUE`` argument on its first colon."""
    name, separator, value = pair.partition(":")
    if not separator:
        raise CommandError(
            f"Invalid pair {pair!r}: expected the form VARIABLE:VALUE."
        )
    name = name.strip()
    if not name:
        raise CommandError(f"Invalid pair {pair!r}: the variable name is empty.")
    return name, value


def _run_save(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    values = dict(_parse_pair(pair) for pair in args.pairs)

    for key in values:
        if is_vault_variable(key):
            warn(
                f"{key} configures the Vault connection itself; NavConfig "
                "reads it from the .env file, not from Vault."
            )

    settings = resolve_settings(args, project_root)
    destination = f"{settings['mount_point']}/{settings['path']}"

    msg(f"Saving {len(values)} variable(s) to {settings['url']} -> {destination}")
    for key, value in values.items():
        msg(f"  {key} = {_mask(value)}")

    if args.dry_run:
        msg("")
        msg("Dry run: nothing was written to Vault.")
        return 0

    writer = VaultWriter(settings)
    payload = writer.read()
    payload.update(values)
    writer.write(payload)

    msg("")
    msg(f"Saved {len(values)} variable(s) to {destination}.")
    return 0
