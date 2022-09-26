from cryptography.fernet import Fernet
from .abstract import AbstractCypher

class FileCypher(AbstractCypher):

    async def create_key(self):
        #generate the key
        key = Fernet.generate_key()
        file = self.path.joinpath('unlock.key')
        #string the key into a file
        await self.save_file(file, key)
        return file

    async def get_key(self):
        try:
            key = await self.read_file('unlock.key')
            if not key:
                raise Exception(
                    'Missing the Unlock Key'
                )
            #use the generated key
            f = Fernet(key)
            return f
        except FileNotFoundError as ex:
            raise FileNotFoundError(
                ex
            ) from ex
        except RuntimeError as ex:
            raise RuntimeError(
                f'NavConfig: Error reading the unlock Key: {ex}'
            ) from ex

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
        return await self.strbuffer(decrypted.decode())
