from typing import Any, Union
from abc import ABC, abstractmethod
import logging
from pathlib import PurePath
from io import StringIO
from dotenv import dotenv_values, load_dotenv
from ..project import validate_project_environment


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
        self.downloadable: bool = False
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
                f"{type(self).__name__}: No Directory Path: {env_path}"
            )

    @abstractmethod
    def load_environment(self):
        pass

    @abstractmethod
    def save_environment(self):
        pass

    def load_from_file(self, path):
        load_dotenv(dotenv_path=path, override=self.override)

    def load_from_stream(self, content: str):
        load_dotenv(stream=content, override=self.override)

    def load_from_string(self, content: Union[str, dict]):
        if not isinstance(content, str):
            return content
        filelike = StringIO(content)
        filelike.seek(0)
        dotenv_values(stream=filelike)

    def load(self):
        # TODO: making some validation of content
        return self._content
