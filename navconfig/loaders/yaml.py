
from typing import (
    Union
)
from pathlib import Path
import codecs
import yaml
from .base import BaseLoader

class YamlLoader(BaseLoader):
    """YamlLoader.

    Used to read configuration settings from YAML files.

    Args:
        BaseLoader (_type_): _description_
    """

    def load_enviroment(self, file: Union[str, Path]):
        with codecs.open(file, 'r') as f:
            content = yaml.safe_load(f)
        self.load_from_string(content)

    def save_enviroment(self):
        pass
