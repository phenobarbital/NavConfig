import os
import asyncio
from navconfig import (
    SITE_ROOT,
    config,
    DEBUG
)
import logging
from navconfig.cyphers import FileCypher
from dotenv import load_dotenv, dotenv_values

async def cypher():
    path = SITE_ROOT.joinpath('env')
    fc = FileCypher(path)
    # first: create the key:
    await fc.create_key()
    # then, encrypt the file:
    file = await fc.encrypt(name = '.env')
    print(f'Encrypted ENV was saved to {file}')

async def test_cypher():
    path = SITE_ROOT.joinpath('env')
    fc = FileCypher(path)
    file = await fc.decrypt(name = 'env.crypt')
    print(file)

async def test_env():
    path = SITE_ROOT.joinpath('env')
    fc = FileCypher(path)
    file = await fc.decrypt(name = 'env.crypt')
    print(file)
    load_dotenv(
        stream=file
    )
    print(os.getenv('ADFS_SERVER'))
    
if __name__ == '__main__':
    asyncio.run(cypher())
    asyncio.run(test_cypher())
    asyncio.run(test_env())