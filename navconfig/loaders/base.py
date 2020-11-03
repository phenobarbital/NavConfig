from abc import ABC, abstractmethod
from io import StringIO
from dotenv import dotenv_values


class BaseLoader(ABC):

    @abstractmethod
    def load_enviroment(self):
        pass

    @abstractmethod
    def save_enviroment(self):
        pass

    def load_from_string(self, content: str):
        filelike = StringIO(content)
        filelike.seek(0)
        dotenv_values(stream=filelike)
