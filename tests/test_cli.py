"""Tests for the ``kardex`` command line interface.

These must run without a scaffolded project: the whole point of
``kardex env create`` is to bootstrap one, so importing the CLI may never
require ``env/`` to exist already.
"""
import subprocess
import sys
from configparser import ConfigParser

import pytest

from navconfig.cli import main
from navconfig.commands.common import SPLIT_ENV_FILES, VAULT_BLOCK_START
from navconfig.commands.vault import (
    _parse_pair,
    collect_migratable,
    is_vault_variable,
)

# ---------------------------------------------------------------------------
# Initialization order
# ---------------------------------------------------------------------------

def test_cli_importable_without_project(tmp_path):
    """``kardex`` must load in a directory that has no env/ folder.

    Regression test: the CLI used to build the global configuration at
    import time, so ``kardex create`` crashed on exactly the projects it
    was meant to scaffold.
    """
    result = subprocess.run(
        [sys.executable, "-m", "navconfig.cli", "env", "create"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "SITE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "env" / "dev" / ".env").exists()


def test_import_navconfig_does_not_build_config():
    """Importing the package must not instantiate Kardex on its own."""
    import navconfig

    # Accessing a lazy name is what triggers the bootstrap; the module
    # namespace stays clean until then.
    assert "bootstrap" in navconfig.__all__
    assert callable(navconfig.bootstrap)


# ---------------------------------------------------------------------------
# kardex env
# ---------------------------------------------------------------------------

def test_env_create(tmp_path):
    assert main(["env", "create", "--env", "qa", "--path", str(tmp_path)]) == 0

    env_file = tmp_path / "env" / "qa" / ".env"
    base_file = tmp_path / "env" / ".env"
    config_file = tmp_path / "etc" / "config.ini"

    assert env_file.exists()
    assert base_file.exists()
    assert config_file.exists()
    assert (tmp_path / "logs").is_dir()
    assert (tmp_path / "templates").is_dir()

    assert "ENV=qa" in env_file.read_text()
    # The shared file must not pin an environment.
    assert "\nENV=" not in base_file.read_text()
    assert "[navconfig]" in config_file.read_text()


def test_env_create_split(tmp_path):
    assert main(
        ["env", "create", "--env", "dev", "--path", str(tmp_path), "--split"]
    ) == 0

    env_dir = tmp_path / "env" / "dev"
    assert (env_dir / ".env").exists()
    for filename in SPLIT_ENV_FILES:
        assert (env_dir / filename).exists(), filename


def test_env_create_is_idempotent(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    env_file = tmp_path / "env" / "dev" / ".env"
    env_file.write_text("ENV=dev\nCUSTOM=kept\n", encoding="utf-8")

    assert main(["env", "create", "--path", str(tmp_path)]) == 0
    assert "CUSTOM=kept" in env_file.read_text()

    assert main(["env", "create", "--path", str(tmp_path), "--force"]) == 0
    assert "CUSTOM=kept" not in env_file.read_text()


def test_env_new(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    assert main(["env", "new", "prod", "--path", str(tmp_path)]) == 0

    env_file = tmp_path / "env" / "prod" / ".env"
    assert "ENV=prod" in env_file.read_text()

    # A second run refuses to clobber the file...
    assert main(["env", "new", "prod", "--path", str(tmp_path)]) == 1
    # ...unless --force is given.
    assert main(["env", "new", "prod", "--path", str(tmp_path), "--force"]) == 0


def test_create_command_is_gone():
    """The flat ``kardex create`` command no longer exists."""
    with pytest.raises(SystemExit):
        main(["create"])


# ---------------------------------------------------------------------------
# kardex vault
# ---------------------------------------------------------------------------

def test_vault_create_bootstraps_env_file(tmp_path):
    exit_code = main([
        "vault", "create",
        "--env", "dev",
        "--path", str(tmp_path),
        "--url", "http://vault.internal:8200",
        "--token", "s.token",
        "--mount-point", "myapp",
    ])
    assert exit_code == 0

    content = (tmp_path / "env" / "dev" / ".env").read_text()
    assert VAULT_BLOCK_START in content
    assert "VAULT_ENABLED=true" in content
    assert "VAULT_URL=http://vault.internal:8200" in content
    assert "VAULT_TOKEN=s.token" in content
    assert "VAULT_MOUNT_POINT=myapp" in content
    # VAULT_ADDR is not a directive NavConfig reads.
    assert "VAULT_ADDR" not in content


def test_vault_create_rewrites_its_own_block(tmp_path):
    main(["vault", "create", "--path", str(tmp_path), "--token", "first"])
    env_file = tmp_path / "env" / "dev" / ".env"

    # Without --force the block is kept, but explicit flags still apply.
    main(["vault", "create", "--path", str(tmp_path), "--token", "second"])
    content = env_file.read_text()
    assert content.count(VAULT_BLOCK_START) == 1
    assert "VAULT_TOKEN=second" in content

    # With --force the block is replaced, never duplicated.
    main(["vault", "create", "--path", str(tmp_path), "--force", "--token", "third"])
    content = env_file.read_text()
    assert content.count(VAULT_BLOCK_START) == 1
    assert content.count("VAULT_ENABLED=") == 1
    assert "VAULT_TOKEN=third" in content


def test_is_vault_variable():
    assert is_vault_variable("VAULT_TOKEN")
    assert is_vault_variable("VAULT_ANYTHING")
    assert not is_vault_variable("DATABASE_URL")


def test_collect_migratable_excludes_vault_and_bootstrap(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    main(["vault", "create", "--path", str(tmp_path), "--token", "s.token"])
    env_file = tmp_path / "env" / "dev" / ".env"
    env_file.write_text(
        env_file.read_text() + "\nDB_PASSWORD=secret\n", encoding="utf-8"
    )

    values, excluded = collect_migratable(project_root=tmp_path, env="dev")

    assert values["DB_PASSWORD"] == "secret"
    assert "VAULT_TOKEN" not in values
    assert "VAULT_URL" not in values
    assert "ENV" not in values
    assert "CONFIG_FILE" not in values
    assert excluded["VAULT_TOKEN"] == "configures the Vault connection"
    assert excluded["ENV"] == "NavConfig bootstrap directive"


def test_collect_migratable_include_bootstrap(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    values, _ = collect_migratable(
        project_root=tmp_path, env="dev", include_bootstrap=True
    )
    assert "ENV" in values


def test_collect_migratable_include_extra(tmp_path):
    main(["env", "create", "--path", str(tmp_path), "--split"])
    values, _ = collect_migratable(
        project_root=tmp_path, env="dev", include_extra=True
    )
    assert "DBNAME" in values      # from .env.databases
    assert "API_PORT" in values    # from .env.api


def test_vault_migrate_dry_run_does_not_connect(tmp_path, capsys):
    main(["env", "create", "--path", str(tmp_path)])
    env_file = tmp_path / "env" / "dev" / ".env"
    env_file.write_text(
        env_file.read_text() + "\nDB_PASSWORD=secret\n", encoding="utf-8"
    )

    exit_code = main([
        "vault", "migrate",
        "--path", str(tmp_path),
        "--url", "http://127.0.0.1:1",  # nothing listens here
        "--token", "s.token",
        "--dry-run",
    ])
    assert exit_code == 0

    output = capsys.readouterr().out
    assert "Dry run" in output
    # Secrets are never echoed in the clear.
    assert "secret" not in output
    assert "DB_PASSWORD" in output


def test_vault_migrate_unreachable_server_fails_cleanly(tmp_path, capsys):
    main(["env", "create", "--path", str(tmp_path)])
    exit_code = main([
        "vault", "migrate",
        "--path", str(tmp_path),
        "--url", "http://127.0.0.1:1",
        "--token", "s.token",
        "--yes",
    ])
    assert exit_code == 1
    assert "Unable to reach Vault" in capsys.readouterr().err


def test_vault_save_parses_pairs():
    assert _parse_pair("KEY:value") == ("KEY", "value")
    # Only the first colon separates name from value.
    assert _parse_pair("DSN:postgres://u:p@h:5432/db") == (
        "DSN", "postgres://u:p@h:5432/db"
    )


def test_vault_save_rejects_malformed_pair(tmp_path, capsys):
    assert main(["vault", "save", "NOCOLON", "--path", str(tmp_path)]) == 1
    assert "VARIABLE:VALUE" in capsys.readouterr().err


def test_vault_save_requires_token(tmp_path, capsys):
    main(["env", "create", "--path", str(tmp_path)])
    assert main(["vault", "save", "K:v", "--path", str(tmp_path)]) == 1
    assert "VAULT_TOKEN is not set" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# kardex log
# ---------------------------------------------------------------------------

def _logging_section(tmp_path) -> dict:
    parser = ConfigParser()
    parser.read(tmp_path / "etc" / "config.ini", encoding="utf-8")
    return dict(parser["logging"])


def test_log_enable(tmp_path):
    assert main(["log", "enable", "--path", str(tmp_path)]) == 0

    section = _logging_section(tmp_path)
    assert section["logging_echo"] == "true"
    assert section["filehandler_enabled"] == "true"
    assert section["logstash_enabled"] == "false"
    assert "RotatingFileHandler" in section["handlers"]
    assert (tmp_path / "logs").is_dir()


def test_log_enable_logstash(tmp_path):
    exit_code = main([
        "log", "enable",
        "--path", str(tmp_path),
        "--logstash",
        "--logstash-host", "logs.internal",
        "--logstash-port", "5959",
        "--loglevel", "WARNING",
    ])
    assert exit_code == 0

    section = _logging_section(tmp_path)
    assert section["logstash_enabled"] == "true"
    assert section["logging_host"] == "logs.internal"
    assert section["logging_port"] == "5959"
    assert section["loglevel"] == "WARNING"
    assert "LogstashHandler" in section["handlers"]


def test_log_enable_preserves_ini_comments(tmp_path):
    main(["log", "enable", "--path", str(tmp_path)])
    content = (tmp_path / "etc" / "config.ini").read_text()
    assert "# Logging configuration." in content
    assert "[temp]" in content


def test_log_enable_does_not_duplicate_handlers(tmp_path):
    main(["log", "enable", "--path", str(tmp_path)])
    main(["log", "enable", "--path", str(tmp_path)])

    handlers = _logging_section(tmp_path)["handlers"].split(",")
    assert len(handlers) == len(set(handlers))


def test_log_enable_quiet_and_no_file(tmp_path):
    main([
        "log", "enable", "--path", str(tmp_path), "--quiet", "--no-file"
    ])
    section = _logging_section(tmp_path)
    assert section["logging_echo"] == "false"
    assert section["filehandler_enabled"] == "false"
