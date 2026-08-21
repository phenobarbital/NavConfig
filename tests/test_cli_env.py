"""Tests for the ``kardex env`` command group.

``kardex env create`` is the command that bootstraps a NavConfig project,
so every test here starts from an empty directory: nothing may require an
``env/`` folder -- or the global configuration -- to already exist.
"""
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest

from navconfig.cli import main
from navconfig.commands.common import BASE_ENV_FILE, SPLIT_ENV_FILES, read_sample
from navconfig.commands.env import (
    _base_env_content,
    create_environment,
    new_environment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def env_lines(path: Path) -> list:
    """Return the active (non commented-out) ``KEY=VALUE`` lines of a file."""
    return [
        line for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def values_of(path: Path) -> dict:
    """Parse a ``.env`` file into a ``{KEY: VALUE}`` mapping."""
    return dict(
        line.split("=", 1) for line in env_lines(path) if "=" in line
    )


def run_cli(tmp_path: Path, *argv: str) -> subprocess.CompletedProcess:
    """Run ``python -m navconfig.cli`` inside *tmp_path*."""
    return subprocess.run(
        [sys.executable, "-m", "navconfig.cli", *argv],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "SITE_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )


# ---------------------------------------------------------------------------
# _base_env_content
# ---------------------------------------------------------------------------

def test_base_env_content_comments_out_the_env_pin():
    """The shared file documents ``ENV`` but never assigns it."""
    body = _base_env_content("APP_NAME=MyApp\nENV=dev\nDEBUG=true\n")

    assert "# ENV=" in body
    assert "\nENV=" not in f"\n{body}"


def test_base_env_content_preserves_every_other_directive():
    body = _base_env_content("APP_NAME=MyApp\nENV=dev\nDEBUG=true\n")

    assert "APP_NAME=MyApp" in body
    assert "DEBUG=true" in body


def test_base_env_content_keeps_comments_and_trailing_newline():
    body = _base_env_content("# a comment\nENV=dev")

    assert body.startswith("# a comment")
    assert body.endswith("\n")


# ---------------------------------------------------------------------------
# create_environment()
# ---------------------------------------------------------------------------

def test_create_environment_reports_every_artifact(tmp_path):
    """The ``created`` mapping is what the CLI prints back to the user."""
    created, skipped = create_environment(env="dev", project_root=tmp_path)

    assert set(created) == {
        "env/.env", "env/dev/.env", "etc/config.ini", "logs/", "templates/"
    }
    assert skipped == {}
    assert all(Path(path).exists() for path in created.values())


def test_create_environment_second_run_skips_existing_files(tmp_path):
    create_environment(env="dev", project_root=tmp_path)
    created, skipped = create_environment(env="dev", project_root=tmp_path)

    assert set(skipped) == {"env/.env", "env/dev/.env", "etc/config.ini"}
    # Directories are idempotent, so they are always reported as created.
    assert set(created) == {"logs/", "templates/"}


def test_create_environment_force_rewrites_files(tmp_path):
    create_environment(env="dev", project_root=tmp_path)
    created, skipped = create_environment(
        env="dev", project_root=tmp_path, force=True
    )

    assert skipped == {}
    assert "env/dev/.env" in created


def test_create_environment_split_writes_the_bundled_samples(tmp_path):
    created, _ = create_environment(
        env="dev", project_root=tmp_path, split=True
    )

    for filename in SPLIT_ENV_FILES:
        label = f"env/dev/{filename}"
        assert label in created, label
        assert created[label].read_text(encoding="utf-8") == read_sample(
            f"{filename}.sample"
        )


def test_create_environment_without_split_creates_no_extra_files(tmp_path):
    create_environment(env="dev", project_root=tmp_path)

    env_dir = tmp_path / "env" / "dev"
    assert sorted(p.name for p in env_dir.iterdir()) == [BASE_ENV_FILE]


# ---------------------------------------------------------------------------
# kardex env create
# ---------------------------------------------------------------------------

def test_env_create_defaults_to_dev(tmp_path):
    assert main(["env", "create", "--path", str(tmp_path)]) == 0

    assert (tmp_path / "env" / "dev" / BASE_ENV_FILE).exists()
    assert values_of(tmp_path / "env" / "dev" / BASE_ENV_FILE)["ENV"] == "dev"


@pytest.mark.parametrize("name", ["prod", "staging", "qa2", "prod-eu"])
def test_env_create_accepts_any_environment_name(tmp_path, name):
    assert main(
        ["env", "create", "--env", name, "--path", str(tmp_path)]
    ) == 0

    env_file = tmp_path / "env" / name / BASE_ENV_FILE
    assert values_of(env_file)["ENV"] == name


def test_env_create_makes_a_missing_project_root(tmp_path):
    """``--path`` may point at a directory that does not exist yet."""
    project = tmp_path / "brand" / "new"

    assert main(["env", "create", "--path", str(project)]) == 0
    assert (project / "env" / "dev" / BASE_ENV_FILE).exists()


def test_env_create_defaults_to_the_current_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert main(["env", "create"]) == 0
    assert (tmp_path / "env" / "dev" / BASE_ENV_FILE).exists()


def test_env_create_shared_file_is_never_pinned(tmp_path):
    main(["env", "create", "--env", "qa", "--path", str(tmp_path)])

    base_file = tmp_path / "env" / BASE_ENV_FILE
    assert "ENV" not in values_of(base_file)
    assert "# ENV=" in base_file.read_text(encoding="utf-8")
    # ...but the rest of the sample is still there to edit.
    assert "CONFIG_FILE" in values_of(base_file)


def test_env_create_writes_a_parseable_ini(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])

    parser = ConfigParser()
    parser.read(tmp_path / "etc" / "config.ini", encoding="utf-8")
    assert parser.has_section("navconfig")


def test_env_create_split_creates_the_supplementary_files(tmp_path):
    assert main(
        ["env", "create", "--path", str(tmp_path), "--split"]
    ) == 0

    env_dir = tmp_path / "env" / "dev"
    assert sorted(p.name for p in env_dir.iterdir()) == sorted(
        (BASE_ENV_FILE, *SPLIT_ENV_FILES)
    )
    assert "API_PORT" in values_of(env_dir / ".env.api")
    assert "DBNAME" in values_of(env_dir / ".env.databases")


def test_env_create_preserves_edits_and_force_discards_them(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    env_file = tmp_path / "env" / "dev" / BASE_ENV_FILE
    env_file.write_text("ENV=dev\nSECRET=keep-me\n", encoding="utf-8")

    assert main(["env", "create", "--path", str(tmp_path)]) == 0
    assert values_of(env_file)["SECRET"] == "keep-me"

    assert main(["env", "create", "--path", str(tmp_path), "--force"]) == 0
    assert "SECRET" not in values_of(env_file)
    assert values_of(env_file)["ENV"] == "dev"


def test_env_create_split_does_not_clobber_supplementary_files(tmp_path):
    main(["env", "create", "--path", str(tmp_path), "--split"])
    local = tmp_path / "env" / "dev" / ".env.local"
    local.write_text("DEBUG=false\n", encoding="utf-8")

    assert main(["env", "create", "--path", str(tmp_path), "--split"]) == 0
    assert local.read_text(encoding="utf-8") == "DEBUG=false\n"


def test_env_create_reports_next_steps(tmp_path, capsys):
    main(["env", "create", "--env", "qa", "--path", str(tmp_path)])

    output = capsys.readouterr().out
    assert str(tmp_path) in output
    assert "created  env/qa/.env" in output
    assert "ENV=qa" in output  # the "Next:" hint


def test_env_create_reports_skipped_files(tmp_path, capsys):
    main(["env", "create", "--path", str(tmp_path)])
    capsys.readouterr()

    main(["env", "create", "--path", str(tmp_path)])
    output = capsys.readouterr().out
    assert "skipped  env/dev/.env" in output
    assert "already exists" in output


# ---------------------------------------------------------------------------
# kardex env new
# ---------------------------------------------------------------------------

def test_env_new_inherits_the_shared_base_file(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])
    base_file = tmp_path / "env" / BASE_ENV_FILE
    base_file.write_text(
        base_file.read_text(encoding="utf-8") + "\nSHARED=yes\n",
        encoding="utf-8",
    )

    assert main(["env", "new", "prod", "--path", str(tmp_path)]) == 0

    values = values_of(tmp_path / "env" / "prod" / BASE_ENV_FILE)
    assert values["SHARED"] == "yes"
    assert values["ENV"] == "prod"


def test_env_new_falls_back_to_the_bundled_sample(tmp_path):
    """``env new`` works on a project that was never scaffolded."""
    assert main(["env", "new", "staging", "--path", str(tmp_path)]) == 0

    env_file = tmp_path / "env" / "staging" / BASE_ENV_FILE
    values = values_of(env_file)
    assert values["ENV"] == "staging"
    assert "CONFIG_FILE" in values


def test_env_new_repins_env_only_once(tmp_path):
    """Whatever the base was pinned to, exactly one ``ENV=`` survives."""
    base_file = tmp_path / "env" / BASE_ENV_FILE
    base_file.parent.mkdir(parents=True)
    base_file.write_text("ENV=dev\nAPP_NAME=MyApp\n", encoding="utf-8")

    main(["env", "new", "prod", "--path", str(tmp_path)])

    lines = env_lines(tmp_path / "env" / "prod" / BASE_ENV_FILE)
    assert lines.count("ENV=prod") == 1
    assert not any(line.startswith("ENV=dev") for line in lines)


def test_env_new_refuses_to_overwrite(tmp_path, capsys):
    main(["env", "new", "prod", "--path", str(tmp_path)])
    env_file = tmp_path / "env" / "prod" / BASE_ENV_FILE
    env_file.write_text("ENV=prod\nSECRET=keep-me\n", encoding="utf-8")

    assert main(["env", "new", "prod", "--path", str(tmp_path)]) == 1

    error = capsys.readouterr().err
    assert "already exists" in error
    assert "--force" in error
    # The refusal must leave the file exactly as it was.
    assert values_of(env_file)["SECRET"] == "keep-me"


def test_env_new_force_overwrites(tmp_path, capsys):
    main(["env", "new", "prod", "--path", str(tmp_path)])
    env_file = tmp_path / "env" / "prod" / BASE_ENV_FILE
    env_file.write_text("ENV=prod\nSECRET=drop-me\n", encoding="utf-8")

    assert main(
        ["env", "new", "prod", "--path", str(tmp_path), "--force"]
    ) == 0

    values = values_of(env_file)
    assert "SECRET" not in values
    assert values["ENV"] == "prod"
    assert "created  env/prod/.env" in capsys.readouterr().out


def test_env_new_split_creates_the_supplementary_files(tmp_path):
    main(["env", "create", "--path", str(tmp_path)])

    assert main(
        ["env", "new", "prod", "--path", str(tmp_path), "--split"]
    ) == 0

    env_dir = tmp_path / "env" / "prod"
    for filename in SPLIT_ENV_FILES:
        assert (env_dir / filename).exists(), filename


def test_env_new_split_skips_existing_files(tmp_path, capsys):
    """A supplementary file that is already there is reported, not rewritten."""
    local = tmp_path / "env" / "prod" / ".env.local"
    local.parent.mkdir(parents=True)
    local.write_text("LOGLEVEL=ERROR\n", encoding="utf-8")

    assert main(
        ["env", "new", "prod", "--path", str(tmp_path), "--split"]
    ) == 0

    assert local.read_text(encoding="utf-8") == "LOGLEVEL=ERROR\n"
    output = capsys.readouterr().out
    assert "skipped  env/prod/.env.local" in output


def test_env_new_split_force_refreshes_existing_files(tmp_path):
    main(["env", "new", "prod", "--path", str(tmp_path), "--split"])
    local = tmp_path / "env" / "prod" / ".env.local"
    local.write_text("LOGLEVEL=ERROR\n", encoding="utf-8")

    assert main(
        ["env", "new", "prod", "--path", str(tmp_path), "--split", "--force"]
    ) == 0
    assert "LOGLEVEL=ERROR" not in local.read_text(encoding="utf-8")


def test_env_new_leaves_sibling_environments_untouched(tmp_path):
    main(["env", "create", "--env", "dev", "--path", str(tmp_path)])
    dev_file = tmp_path / "env" / "dev" / BASE_ENV_FILE
    dev_file.write_text("ENV=dev\nDEV_ONLY=1\n", encoding="utf-8")

    main(["env", "new", "prod", "--path", str(tmp_path)])

    assert values_of(dev_file) == {"ENV": "dev", "DEV_ONLY": "1"}
    assert sorted(
        p.name for p in (tmp_path / "env").iterdir() if p.is_dir()
    ) == ["dev", "prod"]


def test_new_environment_returns_created_and_skipped(tmp_path):
    new_environment(name="prod", project_root=tmp_path, split=True)
    created, skipped = new_environment(
        name="prod", project_root=tmp_path, split=True, force=True
    )

    assert f"env/prod/{BASE_ENV_FILE}" in created
    assert skipped == {}


# ---------------------------------------------------------------------------
# Parser wiring
# ---------------------------------------------------------------------------

def test_env_requires_an_action():
    with pytest.raises(SystemExit) as excinfo:
        main(["env"])
    assert excinfo.value.code == 2


def test_env_rejects_unknown_actions():
    with pytest.raises(SystemExit) as excinfo:
        main(["env", "destroy"])
    assert excinfo.value.code == 2


def test_env_new_requires_a_name():
    with pytest.raises(SystemExit) as excinfo:
        main(["env", "new"])
    assert excinfo.value.code == 2


def test_env_help_lists_both_actions(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["env", "--help"])
    assert excinfo.value.code == 0

    output = capsys.readouterr().out
    assert "create" in output
    assert "new" in output


# ---------------------------------------------------------------------------
# End-to-end, through the installed entry point
# ---------------------------------------------------------------------------

def test_env_new_from_the_command_line_without_a_project(tmp_path):
    """``kardex env new`` must not need a configured project either."""
    result = run_cli(tmp_path, "env", "new", "prod", "--split")

    assert result.returncode == 0, result.stderr
    env_dir = tmp_path / "env" / "prod"
    assert (env_dir / BASE_ENV_FILE).exists()
    assert (env_dir / ".env.local").exists()


def test_env_create_then_new_from_the_command_line(tmp_path):
    assert run_cli(tmp_path, "env", "create").returncode == 0
    result = run_cli(tmp_path, "env", "new", "prod")

    assert result.returncode == 0, result.stderr
    assert "created" in result.stdout
    assert (tmp_path / "env" / "prod" / BASE_ENV_FILE).exists()
