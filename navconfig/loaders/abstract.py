from typing import Any, Union
from abc import ABC, abstractmethod
import logging
import re
from pathlib import PurePath
from io import StringIO
from dotenv import dotenv_values, load_dotenv
from ..project import validate_project_environment


# Matches INI-style section headers (e.g. ``[AUTH_BACKENDS]``) on their own line.
_SECTION_HEADER = re.compile(r"^\s*\[[^\]]*\]\s*$")

# Sentinel returned by ``BaseLoader.reload_key`` when the origin has no value.
KEY_NOT_FOUND = object()


def _strip_section_headers(content: str) -> str:
    """Remove INI-style ``[section]`` lines from a .env file content.

    Some projects use ``.env`` files as if they were ``.ini`` files, grouping
    variables under ``[Section]`` headers. python-dotenv parses those headers
    as keys with a ``None`` value (e.g. ``"[AUTH_BACKENDS]": None``), polluting
    the environment. This filter drops those lines before they reach dotenv.

    Args:
        content: Raw text content of a .env file.

    Returns:
        The same content without lines that are pure section headers.
    """
    return "\n".join(
        line for line in content.splitlines()
        if not _SECTION_HEADER.match(line)
    )


class BaseLoader(ABC):
    def __init__(
        self,
        env_path: PurePath = None,
        override: bool = False,
        create: bool = True,
        **kwargs,
    ) -> None:
        self.override: bool = override
        self.env_path = env_path
        self.env_file = ".env"
        self._kwargs = kwargs
        self._content: Any = None
        if isinstance(self.env_path, PurePath) and not env_path.exists():
            if create:
                try:
                    env_path.mkdir(parents=True, exist_ok=True)
                except IOError as ex:
                    raise RuntimeError(
                        f"{type(self).__name__}: Error creating directory {env_path}: {ex}"  # noqa
                    ) from ex
            env_status, warnings = validate_project_environment()
            if env_status != 'ok':
                for warning in warnings:
                    logging.warning(f"NavConfig: {warning}")
            raise FileExistsError(
                "NavConfig could not find the expected environment directory. "
                f"Looked for: {env_path}.\n"
                "NavConfig projects require an 'env/<environment>/.env' file. "
                "Run `kardex env create` to scaffold the default structure (env folder, "
                "base .env file, and etc/config.ini)."
            )

    @abstractmethod
    def load_environment(self):
        pass

    @abstractmethod
    def save_environment(self):
        pass

    def reload_key(self, key: str) -> Any:
        """Re-read a single variable straight from this loader's origin.

        Bypasses ``os.environ`` and any in-memory mapping. Loaders that can
        not resolve one key in isolation keep this default.

        Args:
            key: Variable name.

        Returns:
            The value at the origin, or ``KEY_NOT_FOUND``.
        """
        return KEY_NOT_FOUND

    def _read_key_from_files(
        self, key: str, patterns: list, first_wins: bool = True
    ) -> Any:
        """Read ``key`` from the ``.env`` files in ``patterns`` order.

        Mirrors the loaders' precedence: with ``first_wins`` the first file
        defining the key wins (``load_dotenv(override=False)``), otherwise
        the last one does.

        Args:
            key: Variable name.
            patterns: File names relative to ``env_path``.
            first_wins: Stop at the first file defining the key.

        Returns:
            The value, or ``KEY_NOT_FOUND``.
        """
        found = KEY_NOT_FOUND
        if not isinstance(self.env_path, PurePath):
            return found
        for name in patterns:
            path = self.env_path / name
            try:
                if not path.is_file() or path.stat().st_size == 0:
                    continue
                with open(path, "r", encoding="utf-8") as fh:
                    content = _strip_section_headers(fh.read())
            except OSError as err:
                logging.debug(f"NavConfig: unable to read {path}: {err}")
                continue
            values = dotenv_values(stream=StringIO(content))
            if values.get(key) is not None:
                found = values[key]
                if first_wins:
                    break
        return found

    def load_from_file(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            content = _strip_section_headers(fh.read())
        load_dotenv(stream=StringIO(content), override=self.override)

    def load_from_stream(self, content: str):
        content = _strip_section_headers(content)
        load_dotenv(stream=StringIO(content), override=self.override)

    def load_from_string(self, content: Union[str, dict]):
        if not isinstance(content, str):
            return content
        filelike = StringIO(_strip_section_headers(content))
        filelike.seek(0)
        dotenv_values(stream=filelike)

    def load(self):
        # TODO: making some validation of content
        return self._content
