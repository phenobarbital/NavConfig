import hashlib
import aiofiles
from cryptography.fernet import Fernet
from pathlib import PurePath, PosixPath
from io import StringIO

    
class FileCypher(object):
    def __init__(self, directory: PurePath):
        self.path = directory

    async def create_key(self):
        #generate the key
        key = Fernet.generate_key()
        file = self.path.joinpath('unlock.key')
        #string the key into a file
        async with aiofiles.open(file, 'wb') as unlock:
            await unlock.write(key)
        return file
    
    async def open_file(self, path: PurePath):
        content = None
        if not path.exists():
            raise FileNotFoundError(
                f'File {path} does not exist'
            )
        try:
            async with aiofiles.open(path) as f:
                content = await f.read()
        except IOError:
            raise Exception(
                f'NavConfig: Error loading Environment File {path}'
            )
        return content
    
    async def save_file(self, path: PurePath, content):
        async with aiofiles.open(path, 'wb') as file:
            await file.write(content)
    
    async def get_key(self):
        fkey = self.path.joinpath('unlock.key')
        key = None
        async with aiofiles.open(fkey) as f:
            key = await f.read()
        if not key:
            raise Exception(
                f'Missing the Unlock Key: {fkey!s}'
            )
        #use the generated key
        f = Fernet(key)
        return f
    
    async def encrypt(self, name: str = '.env'):
        #use the generated key
        f = await self.get_key()
        file = self.path.joinpath(name)
        # original content
        original = await self.open_file(file)
        #encrypt the file
        encrypted = f.encrypt(original.encode())
        # at now, save it into the same directory
        file = self.path.joinpath('env.crypt')
        await self.save_file(file, encrypted)
        return file
    
    async def decrypt(self, name: str = 'env.crypt'):
        #use the generated key
        f = await self.get_key()
        #open the original file to encrypt
        file = self.path.joinpath(name)
        content = await self.open_file(file)
        #decrypt the file
        decrypted = f.decrypt(content.encode())
        s = StringIO()
        s.write(decrypted.decode())
        s.seek(0)
        # returned a StringIO
        return s