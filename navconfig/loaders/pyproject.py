import asyncio
from pathlib import PurePath
from .parsers.toml import TOMLParser
from .abstract import BaseLoader

class pyProjectLoader(BaseLoader):
    """pyProjectLoader.

    Read Configuration from a pyproject.toml (TOML syntax) file.
    """
    def __init__(
        self,
        env_path: PurePath,
        override: bool = False,
        project_name: str = None,
        project_file: str = 'pyproject.toml',
        **kwargs
    ) -> None:
        self.project_name = project_name
        super().__init__(env_path, override, **kwargs)
        self.env_file = self.env_path.joinpath(project_file)
        if not self.env_file.exists():
            raise FileNotFoundError(
                f"Config File Not Found: {self.env_file}"
            )
        self._parser = TOMLParser()

    def load_environment(self):
        self._content = asyncio.run(
            self._parser.parse(self.env_file)
        )
        return self.load().get(self.project_name, {})

    def save_environment(self):
        pass
