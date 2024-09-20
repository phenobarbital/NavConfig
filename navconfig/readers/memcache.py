import os
import logging
import pylibmc
from ..exceptions import ReaderNotSet
from .abstract import AbstractReader


class mcache(AbstractReader):
    """
    Basic Connector for Memcached.
    Future-proof.
    """

    _args = {"tcp_nodelay": True, "ketama": True}

    def __init__(self) -> None:
        host = os.getenv("MEMCACHE_HOST", "localhost")
        port = int(os.getenv("MEMCACHE_PORT", "11211"))
        try:
            self._server = [f"{host}:{port}"]
            self._memcached = pylibmc.Client(
                self._server, binary=True, behaviors=self._args
            )
            # Set a temporary value
            self._memcached.set("ping", "pong", time=1)
        except pylibmc.ConnectionError as err:
            self.enabled = False
            raise ReaderNotSet(
                f"Unable to Connect: {err} :: Memcached Disabled ::"
            ) from err
        except Exception as err:  # pylint: disable=W0703
            self.enabled = False
            logging.exception(err, stack_info=True)

    def get(self, key, default=None):
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            result = self._memcached.get(bytes(key, "utf-8"), default)
            if result:
                return result.decode("utf-8")
            else:
                return None
        except Exception as err:
            raise Exception(f"Memcache Get Error: {err!s}") from err

    def exists(self, key: str) -> bool:
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            result = self._memcached.get(bytes(key, "utf-8"))
            if result:
                return True
            else:
                return False
        except Exception:  # pylint: disable=W0703
            return False

    def set(self, key, value, timeout: int = None):
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            if timeout:
                return self._memcached.set(
                    bytes(key, "utf-8"), bytes(value, "utf-8"), time=timeout
                )
            else:
                return self._memcached.set(
                    bytes(key, "utf-8"),
                    bytes(value, "utf-8")
                )
        except Exception as err:
            raise Exception(f"Memcache Set Error: {err!s}") from err

    def multi_get(self, *keys):
        try:
            return self._memcached.multi_get(
                *[bytes(v, "utf-8") for v in keys]
            )
        except Exception as err:
            raise Exception(f"Memcache Multi Error: {err!s}") from err

    def delete(self, key):
        try:
            self._memcached.delete(bytes(key, "utf-8"))
        except Exception as err:
            raise Exception(f"Memcache Delete Error: {err!s}") from err

    def close(self):
        try:
            self._memcached.disconnect_all()
        except Exception as err:  # pylint: disable=W0703
            logging.exception(err, stack_info=False)
