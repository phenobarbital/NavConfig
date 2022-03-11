import codecs
import toml
from pathlib import Path
from .base import BaseLoader
from typing import (
    Union
)

class TomlLoader(BaseLoader):
    """TomlLoader.
    
    Used to read configuration settings from TOML files.

    Args:
        BaseLoader (_type_): _description_
    """

    def load_enviroment(self, file: Union[str, Path]):
        with codecs.open(file, 'r') as f:
            content = toml.loads(f.read())
        self.load_from_string(content)

    def save_enviroment(self):
        pass