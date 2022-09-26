import os
import logging
import aiomcache

class mcache(object):
    """
    Basic Connector for Memcached.
    Future-proof.
    """
    def __init__(self) -> None:
        host = os.getenv('MEMCACHE_HOST', 'localhost')
        port = int(os.getenv('MEMCACHE_PORT', '11211'))
        try:
            self._memcached = aiomcache.Client(
                host=host, port=port
            )
        except Exception as err: # pylint: disable=W0703
            logging.exception(err, stack_info=True)

    async def get(self, key, default=None):
        try:
            result = await self._memcached.get(bytes(key, "utf-8"), default)
            if result:
                return result.decode("utf-8")
            else:
                return None
        except Exception as err:
            raise Exception(
                f"Memcache Get Error: {err!s}"
            ) from err

    async def set(self, key, value, timeout: int = None):
        try:
            if timeout:
                return await self._memcached.set(
                    bytes(key, "utf-8"), bytes(value, "utf-8"), time=timeout
                )
            else:
                return await self._memcached.set(
                    bytes(key, "utf-8"), bytes(value, "utf-8")
                )
        except Exception as err:
            raise Exception(
                f"Memcache Set Error: {err!s}"
            ) from err

    async def multi_get(self, *keys):
        try:
            return await self._memcached.multi_get(
                *[bytes(v, 'utf-8') for v in keys]
            )
        except Exception as err:
            raise Exception(
                f"Memcache Multi Error: {err!s}"
            ) from err

    async def delete(self, key):
        try:
            await self._memcached.delete(bytes(key, "utf-8"))
        except Exception as err:
            raise Exception(
                f"Memcache Delete Error: {err!s}"
            ) from err

    async def close(self):
        try:
            await self._memcached.close()
        except Exception as err: # pylint: disable=W0703
            logging.exception(err, stack_info=False)
