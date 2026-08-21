"""``kardex log`` -- turn NavConfig's logging facility on."""
from __future__ import annotations

import argparse
from configparser import ConfigParser
from pathlib import Path

from .common import msg, read_sample, resolve_root, warn

#: Section of ``etc/config.ini`` read by ``navconfig.logging``.
LOGGING_SECTION = "logging"


def _load_ini(config_file: Path) -> tuple[str, ConfigParser, bool]:
    """Return the INI text and parser, creating the file when missing."""
    created = False
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(read_sample("config.ini.sample"), encoding="utf-8")
        created = True

    content = config_file.read_text(encoding="utf-8")
    parser = ConfigParser()
    parser.read_string(content, source=str(config_file))
    return content, parser, created


def set_ini_option(content: str, section: str, key: str, value: str) -> str:
    """Return *content* with ``key = value`` set inside ``[section]``.

    ``configparser`` drops every comment when it writes a file back, which
    would throw away the documentation shipped in ``config.ini.sample`` on
    the very first run. This rewrites the assignment line in place instead,
    so the surrounding comments survive.
    """
    lines = content.splitlines()
    header = f"[{section}]"
    assignment = f"{key} = {value}"

    start = None
    for index, line in enumerate(lines):
        if line.strip() == header:
            start = index + 1
            break

    if start is None:
        # The section is missing entirely: append it with this single option.
        body = "\n".join(lines).rstrip()
        return f"{body}\n\n{header}\n{assignment}\n"

    end = len(lines)
    for index in range(start, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break

    for index in range(start, end):
        candidate = lines[index].lstrip("#").strip()
        if "=" not in candidate:
            continue
        # configparser is case-insensitive on option names.
        if candidate.split("=", 1)[0].strip().lower() == key.lower():
            lines[index] = assignment
            return "\n".join(lines) + "\n"

    # Not present yet: append it after the last non-blank line of the section.
    insert_at = end
    while insert_at > start and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, assignment)
    return "\n".join(lines) + "\n"


def _handler_list(parser: ConfigParser, wanted: list) -> str:
    """Merge *wanted* handlers into the configured handler list."""
    current = parser.get(LOGGING_SECTION, "handlers", fallback="console")
    handlers = [name.strip() for name in current.split(",") if name.strip()]
    for name in wanted:
        if name not in handlers:
            handlers.append(name)
    return ",".join(handlers)


def enable_logging(
    project_root: Path,
    loglevel: str = None,
    logdir: str = None,
    echo: bool = True,
    filehandler: bool = True,
    logstash: bool = False,
    logstash_host: str = None,
    logstash_port: int = None,
    logstash_level: str = None,
    mailer: bool = False,
) -> tuple[Path, dict]:
    """Enable the ``[logging]`` section of ``etc/config.ini``.

    NavConfig reads its logging configuration from that section; this
    command writes it so ``dictConfig(logging_config)`` produces a working
    setup without hand-editing the INI file.

    Args:
        project_root: Project root directory.
        loglevel: Level applied to the console and file handlers.
        logdir: Directory rotating log files are written to.
        echo: Send log records to the console.
        filehandler: Enable the rotating file handler.
        logstash: Enable the asynchronous Logstash handler.
        logstash_host: Host of the Logstash server.
        logstash_port: TCP port of the Logstash server.
        logstash_level: Minimum level forwarded to Logstash.
        mailer: Send an email on CRITICAL records.

    Returns:
        A ``(config_file, settings)`` pair, where *settings* holds the
        values written to the ``[logging]`` section.
    """
    config_file = project_root / "etc" / "config.ini"
    content, parser, created = _load_ini(config_file)

    settings: dict = {
        "logdir": logdir or parser.get(LOGGING_SECTION, "logdir", fallback="logs"),
        "loglevel": (
            loglevel
            or parser.get(LOGGING_SECTION, "loglevel", fallback="INFO")
        ).upper(),
        "logging_echo": str(echo).lower(),
        "filehandler_enabled": str(filehandler).lower(),
        "logstash_enabled": str(logstash).lower(),
        "mailer_enabled": str(mailer).lower(),
        "logging_disable_other": parser.get(
            LOGGING_SECTION, "logging_disable_other", fallback="false"
        ),
    }

    handlers = ["console"] if echo else []
    if filehandler:
        handlers.extend(["RotatingFileHandler", "ErrorFileHandler"])

    if logstash:
        settings["logging_host"] = logstash_host or parser.get(
            LOGGING_SECTION, "logging_host", fallback="localhost"
        )
        settings["logging_port"] = str(
            logstash_port
            if logstash_port is not None
            else parser.get(LOGGING_SECTION, "logging_port", fallback="5044")
        )
        settings["logstash_logging"] = (
            logstash_level
            or parser.get(LOGGING_SECTION, "logstash_logging", fallback="INFO")
        ).upper()
        settings["logstash_flush_timeout"] = parser.get(
            LOGGING_SECTION, "logstash_flush_timeout", fallback="10"
        )
        handlers.append("LogstashHandler")

    if mailer:
        handlers.append("CriticalMailHandler")

    settings["handlers"] = _handler_list(parser, handlers)

    for key, value in settings.items():
        content = set_ini_option(content, LOGGING_SECTION, key, value)
    config_file.write_text(content, encoding="utf-8")

    # The rotating file handler does not create its own directory.
    log_path = Path(settings["logdir"])
    if not log_path.is_absolute():
        log_path = project_root / log_path
    log_path.mkdir(parents=True, exist_ok=True)

    settings["_created_ini"] = created
    return config_file, settings


def _logstash_installed() -> bool:
    try:
        import logstash_async  # noqa: F401  # pylint: disable=W0611
    except ModuleNotFoundError:
        return False
    return True


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``log`` command group."""
    parser = subparsers.add_parser(
        "log",
        help="Configure the NavConfig logging facility.",
        description="Configure the NavConfig logging facility.",
    )
    actions = parser.add_subparsers(dest="action", required=True)

    enable = actions.add_parser(
        "enable",
        help="Enable the [logging] section of etc/config.ini.",
        description=(
            "Write the [logging] section of etc/config.ini, creating the "
            "file from the bundled sample when missing. Console and "
            "rotating-file logging are enabled by default; add --logstash "
            "to also forward records to a Logstash server."
        ),
    )
    enable.add_argument(
        "--path",
        default=".",
        help="Project root directory (default: current directory).",
    )
    enable.add_argument(
        "--loglevel",
        default=None,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Level applied to the console and file handlers.",
    )
    enable.add_argument(
        "--logdir",
        default=None,
        help="Directory rotating log files are written to (default: logs).",
    )
    enable.add_argument(
        "--quiet",
        action="store_true",
        default=False,
        help="Do not echo log records to the console.",
    )
    enable.add_argument(
        "--no-file",
        action="store_true",
        default=False,
        help="Do not enable the rotating file handler.",
    )
    enable.add_argument(
        "--logstash",
        action="store_true",
        default=False,
        help="Enable the asynchronous Logstash handler.",
    )
    enable.add_argument(
        "--logstash-host",
        default=None,
        help="Host of the Logstash server (default: localhost).",
    )
    enable.add_argument(
        "--logstash-port",
        default=None,
        type=int,
        help="TCP port of the Logstash server (default: 5044).",
    )
    enable.add_argument(
        "--logstash-level",
        default=None,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Minimum level forwarded to Logstash (default: INFO).",
    )
    enable.add_argument(
        "--mailer",
        action="store_true",
        default=False,
        help="Send an email on CRITICAL records.",
    )
    enable.set_defaults(func=_run_enable)


def _run_enable(args: argparse.Namespace) -> int:
    project_root = resolve_root(args.path)
    config_file, settings = enable_logging(
        project_root=project_root,
        loglevel=args.loglevel,
        logdir=args.logdir,
        echo=not args.quiet,
        filehandler=not args.no_file,
        logstash=args.logstash,
        logstash_host=args.logstash_host,
        logstash_port=args.logstash_port,
        logstash_level=args.logstash_level,
        mailer=args.mailer,
    )
    created_ini = settings.pop("_created_ini")

    if created_ini:
        msg(f"Created {config_file} from the bundled sample.")
    msg(f"Logging enabled in {config_file}")
    for key, value in settings.items():
        msg(f"  {key} = {value}")

    if args.logstash and not _logstash_installed():
        warn(
            "Logstash is enabled but 'python-logstash-async' is not "
            "installed. Run: pip install navconfig[logstash]"
        )

    msg("")
    msg("Apply it in your application with:")
    msg("  from logging.config import dictConfig")
    msg("  from navconfig.logging import logging_config")
    msg("  dictConfig(logging_config)")
    return 0
