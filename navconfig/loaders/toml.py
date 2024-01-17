import asyncio
from pathlib import PurePath
from .parsers.toml import TOMLParser
from .abstract import BaseLoader


class tomlLoader(BaseLoader):
    """TomlLoader.

    Used to read configuration settings from TOML files.
    """

    def __init__(self, env_path: PurePath, override: bool = False, **kwargs) -> None:
        super().__init__(env_path, override, **kwargs)
        self.env_file = self.env_path.joinpath("env.toml")
        self._parser = TOMLParser()

    def load_environment(self):
        content = asyncio.run(self._parser.parse(self.env_file))
        return self.load_from_string(content)

    def save_environment(self):
        pass
