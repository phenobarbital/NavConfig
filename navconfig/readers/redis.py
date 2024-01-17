import os
import logging
from collections.abc import Callable
import redis
from redis.exceptions import RedisError, ResponseError, ReadOnlyError
from ..exceptions import ReaderNotSet
from .abstract import AbstractReader


class mredis(AbstractReader):
    """
    Very Basic Connector for Redis.
    """

    params: dict = {
        "encoding": "utf-8",
        "decode_responses": True,
        "max_connections": 10,
    }

    def __init__(self):
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "1"))
        self.redis_url = f"redis://{host}:{port}/{db}"
        self._redis: Callable = None
        try:
            self._redis = redis.from_url(url=self.redis_url, **self.params)
            response = self._redis.ping()
            if not response:
                self.enabled = False
        except (ConnectionError, RedisError) as err:
            self.enabled = False
            raise ReaderNotSet(
                f"Unable to Connecto to Redis: {err} :: Redis Disabled ::"
            )
        except TimeoutError as err:
            self.enabled = False
            raise Exception(f"Redis Config: Redis Timeout: {err}") from err
        except Exception as err:
            self.enabled = False
            logging.exception(err)
            raise

    def set(self, key, value):
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            return self._redis.set(key, value)
        except ReadOnlyError as err:
            raise Exception(f"Redis is Read Only: {err}") from err
        except Exception as err:
            raise Exception(f"Redis Error: {err}") from err

    def delete(self, key: str) -> None:
        pass

    def exists(self, key, *keys):
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            return bool(self._redis.exists(key, *keys))
        except ResponseError as err:
            raise Exception(f"Bad Response: {err}") from err
        except RedisError as err:
            raise Exception(f"Redis Error: {err}") from err
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}") from err

    def get(self, key):
        if self.enabled is False:
            raise ReaderNotSet()
        try:
            return self._redis.get(key)
        except ResponseError as err:
            raise Exception(f"Bad Response: {err}") from err
        except RedisError as err:
            raise Exception(f"Redis Error: {err}") from err
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}") from err

    def setex(self, key, value, timeout):
        """
        setex
           Set the value and expiration of a Key
           params:
            key: key Name
            value: value of the key
            timeout: expiration time in seconds
        """
        if self.enabled is False:
            raise ReaderNotSet()
        if not isinstance(timeout, int):
            time = 900
        else:
            time = timeout
        try:
            self._redis.setex(key, time, value)
        except ReadOnlyError as err:
            raise Exception(f"Redis is Read Only: {err}") from err
        except ResponseError as err:
            raise Exception(f"Bad Response: {err}") from err
        except RedisError as err:
            raise Exception(f"Redis Error: {err}") from err
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}") from err

    def close(self):
        try:
            self._redis.close()
        except Exception as err:  # pylint: disable=W0703
            logging.error(err)
