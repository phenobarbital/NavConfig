import asyncio
from pathlib import PurePath
from navconfig.cyphers import FileCypher
# TODO: load by configuration the Cypher.
from .abstract import BaseLoader


class cryptLoader(BaseLoader):
    """cryptLoader.

    Use to read configuration settings from Encrypted Files.
    """
    def __init__(self, env_path: PurePath, override: bool = False, create: bool = True, **kwargs) -> None:
        super().__init__(env_path, override, create=create, **kwargs)
        self.env_file = 'env.crypt'
        self._cypher = FileCypher(directory = env_path)

    def load_environment(self):
        try:
            decrypted = asyncio.run(
                self._cypher.decrypt(name = self.env_file)
            )
            self.load_from_stream(
                content=decrypted
            )
        except FileNotFoundError:
            raise
        except Exception as err:
            print(err)
            raise

    def save_environment(self):
        raise NotImplementedError
