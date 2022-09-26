from abc import abstractmethod
from pathlib import PurePath
from io import StringIO
import aiofiles


class AbstractCypher:
    def __init__(self, directory: PurePath):
        self.path = directory

    async def open_file(self, path: PurePath):
        content = None
        if not path.exists():
            raise FileNotFoundError(
                f'Cypher: File {path} does not exist'
            )
        try:
            async with aiofiles.open(path) as f:
                content = await f.read()
        except IOError as ex:
            raise Exception(
                f'NavConfig: Error loading Environment File {path}'
            ) from ex
        return content

    async def save_file(self, path: PurePath, content, mode: str = 'wb'):
        async with aiofiles.open(path, mode) as file:
            await file.write(content)


    async def read_file(self, filename) -> str:
        fpath = self.path.joinpath(filename)
        if not fpath.exists():
            raise FileNotFoundError(
                f"Not Found: {fpath}"
            )
        content = None
        try:
            async with aiofiles.open(fpath) as f:
                content = await f.read()
            return content
        except IOError as ex:
            raise RuntimeError(
                f'NavConfig: Error reading {fpath}: {ex}'
            ) from ex

    async def strbuffer(self, content):
        s = StringIO()
        s.write(content)
        s.seek(0)
        return s

    @abstractmethod
    async def encrypt(self, name: str = '.env'):
        pass

    @abstractmethod
    async def decrypt(self, name: str = 'env.crypt'):
        pass
