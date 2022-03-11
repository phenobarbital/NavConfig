import os
import ast
from distutils.util import strtobool
import importlib
import sys
import types
import logging
from configparser import ConfigParser
from pathlib import Path
from dotenv import load_dotenv
import redis
from redis.exceptions import (
    ConnectionError,
    RedisError,
    TimeoutError,
    ResponseError,
    ReadOnlyError
)
import pylibmc
from typing import (
    Dict,
    Any,
    Union,
    List
)


class mredis(object):
    """
    Very Basic Connector for Redis.
    """
    params: Dict = {
        "socket_timeout": 60,
        "encoding": 'utf-8',
        "decode_responses": True
    }

    def __init__(self):
        host = os.getenv('REDISHOST', 'localhost')
        port = os.getenv('REDISPORT', 6379)
        db = os.getenv('REDIS_DB', 0)
        try:
            REDIS_URL = "redis://{}:{}/{}".format(host, port, db)
            self._pool = redis.ConnectionPool.from_url(
                url=REDIS_URL, **self.params
            )
            self._redis = redis.Redis(
                connection_pool=self._pool, **self.params
            )
        except (TimeoutError) as err:
            raise Exception(
                f"Redis Config: Redis Timeout: {err}"
            )
        except (RedisError, ConnectionError) as err:
            raise Exception(
                f"Redis Config: Unable to connect to Redis: {err}"
            )
        except Exception as err:
            logging.exception(err)
            raise

    def set(self, key, value):
        try:
            return self._redis.set(key, value)
        except (ReadOnlyError) as err:
            raise Exception(f"Redis is Read Only: {err}")
        except Exception as err:
            raise Exception(f"Redis Error: {err}")

    def get(self, key):
        try:
            return self._redis.get(key)
        except (RedisError, ResponseError) as err:
            raise Exception(f"Redis Error: {err}")
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}")

    def exists(self, key, *keys):
        try:
            return bool(self._redis.exists(key, *keys))
        except (RedisError, ResponseError) as err:
            raise Exception(f"Redis Error: {err}")
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}")

    def setex(self, key, value, timeout):
        """
        setex
           Set the value and expiration of a Key
           params:
            key: key Name
            value: value of the key
            timeout: expiration time in seconds
        """
        if not isinstance(timeout, int):
            time = 900
        else:
            time = timeout
        try:
            self._redis.setex(key, time, value)
        except (ReadOnlyError) as err:
            raise Exception(f"Redis is Read Only: {err}")
        except (RedisError, ResponseError) as err:
            raise Exception(f"Redis Error: {err}")
        except Exception as err:
            raise Exception(f"Unknown Redis Error: {err}")

    def close(self):
        try:
            self._redis.close()
            self._pool.disconnect(inuse_connections=True)
        except Exception as err:
            logging.exception(err)
            raise


class mcache(object):
    """
    Basic Connector for Memcached
    """
    args: Dict = {
        "tcp_nodelay": True,
        "ketama": True
    }
    _memcached = None

    def __init__(self):
        host = os.getenv('MEMCACHE_HOST', 'localhost')
        port = os.getenv('MEMCACHE_PORT', 11211)
        mserver = ["{}:{}".format(host, port)]
        self._memcached = pylibmc.Client(
            mserver, binary=True, behaviors=self.args
        )

    def get(self, key, default=None):
        try:
            result = self._memcached.get(bytes(key, "utf-8"), default)
            if result:
                return result.decode("utf-8")
            else:
                return None
        except (pylibmc.Error) as err:
            raise Exception("Get Memcache Error: {}".format(str(err)))
        except Exception as err:
            raise Exception("Memcache Unknown Error: {}".format(str(err)))

    def set(self, key, value, timeout=None):
        try:
            if timeout:
                return self._memcached.set(
                    bytes(key, "utf-8"), bytes(value, "utf-8"), time=timeout
                )
            else:
                return self._memcached.set(
                    bytes(key, "utf-8"), bytes(value, "utf-8")
                )
        except (pylibmc.Error) as err:
            raise Exception("Set Memcache Error: {}".format(str(err)))
        except Exception as err:
            raise Exception("Memcache Unknown Error: {}".format(str(err)))

    def close(self):
        self._memcached.disconnect_all()


#### TODO: Feature Toggles
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                Singleton, cls).__new__(cls, *args, **kwargs)
            setattr(cls, '__initialized', True)
        return cls._instances[cls]


class navigatorConfig(metaclass=Singleton):
    """
    navigatorConfig.
        Class for Application configuration.
    """
    _mem: mcache = None
    _redis: mredis = None
    _conffile: str = 'etc/config.ini'
    __initialized = False

    def __init__(self, site_root: str = None, env: str = None):
        if self.__initialized is True:
            return
        self.__initialized = True
        # this only load at first time
        if not site_root:
            self._site_path = Path(__file__).resolve().parent.parent
        else:
            self._site_path = Path(site_root).resolve()
        # get redis connection
        try:
            self._redis = mredis()
        except Exception as err:
            raise
        # get memcache connection
        try:
            self._mem = mcache()
        except Exception as err:
            raise
        # then: configure the instance:
        self.configure(env)

    def __del__(self):
        try:
            self._mem.close()
            self._redis.close()
        finally:
            pass

    @property
    def debug(self):
        return self._debug
    
    def configure(self, env: str = None, env_type: str = 'file', override: bool = False):
        # Environment Configuration:
        if env is not None:
            self.ENV = env
        else:
            environment = os.getenv('ENV', '')
            self.ENV = environment
        # getting type of enviroment consumer:
        env_type = os.getenv('NAVCONFIG_ENV', env_type)  # file by default
        try:
            self.load_enviroment(env_type, override=override)
        except FileNotFoundError:
            logging.error(
                'NavConfig Error: Environment (.env) File Missing.'
            )
        # define debug
        self._debug = bool(strtobool(os.getenv('DEBUG', 'False')))
        # and get the config file declared in the environment file
        config_file = os.getenv('CONFIG_FILE', self._conffile)
        self._ini = ConfigParser()
        cf = Path(config_file).resolve()
        if not cf.exists():
            # try ini file from etc/ directory.
            cf = self._site_path.joinpath('etc', self._conffile)
        try:
            self._ini.read(cf)
        except (IOError, Exception) as err:
            logging.exception(
                f"NavConfig: INI file doesn't exist: {err}"
            )

    def save_environment(self, env_type: str = 'drive'):
        """
        Save remote Environment into a local File.
        """
        env_path = self.site_root.joinpath('env', self.ENV, '.env')
        # pluggable types
        if env_type == 'drive':
            from navconfig.loaders import driveLoader
            try:
                d = driveLoader()
                d.save_enviroment(env_path)
            except Exception as err:
                print('Error Saving Environment', err)

    def load_enviroment(self, env_type: str = 'file', file: Union[str, Path] = None, override: bool = False):
        """
        Load an environment from a File or any pluggable Origin.
        """
        if env_type == 'file':
            env_path = self.site_root.joinpath('env', self.ENV, '.env')
            logging.debug(f'Environment File: {env_path!s}')
            # warning if env_path is an empty file or doesn't exists
            if env_path.exists():
                if os.stat(str(env_path)).st_size == 0:
                    raise FileExistsError(
                        f'Empty Environment File: {env_path}'
                    )
                # load dotenv
                load_dotenv(
                    dotenv_path=env_path,
                    override=override
                )
            else:
                raise FileNotFoundError(
                    f'Environment file not found: {env_path}'
                )
        else:
            # TODO: add pluggable types
            if env_type == 'drive':
                from navconfig.loaders import driveLoader
                try:
                    d = driveLoader()
                    d.load_enviroment()
                except Exception as err:
                    logging.exception(
                        f'Error Reading from Google Drive {err}', exc_info=True
                    )
            elif env_type == 'yaml':
                from navconfig.loaders import YamlLoader
                try:
                    d = YamlLoader().load_environment(file)
                except Exception as err:
                    logging.exception(
                        f'Error Reading from YAML File {file}: {err}', exc_info=True
                    )
            elif env_type == 'toml':
                from navconfig.loaders import TomlLoader
                try:
                    d = TomlLoader().load_environment(file)
                except Exception as err:
                    logging.exception(
                        f'Error Reading from TOML File {file}: {err}', exc_info=True
                    )

    @property
    def site_root(self):
        return self._site_path

    @property
    def ini(self):
        """
        ini.
            Returns a INI parser instance
        """
        return self._ini

    def addFiles(self, files):
        """
        addFiles.
            Add new files to the ini parser
        """
        self._ini.read(files)

    def addEnv(self, file):
        if file.exists() and file.is_file():
            try:
                load_dotenv(
                    dotenv_path=file,
                    override=False
                )
            except Exception as err:
                raise
        else:
            raise Exception('Failed to load a new ENV file')

    def getboolean(self, key: str, section: str = None, fallback: Any = None):
        """
        getboolean.
            Interface for getboolean function of ini parser
        """
        val = None
        # if not val and if section, get from INI
        if section is not None:
            try:
                val = self._ini.getboolean(section, key)
                return val
            except ValueError:
                val = self._ini.get(section, key)
                if not val:
                    return fallback
                else:
                    return self._ini.BOOLEAN_STATES[val.lower()]
            except Exception:
                return fallback
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)

        if self._redis.exists(key):
            val = self._redis.get(key)

        if not val:
            val = self._mem.get(key)

        if val:
            if val.lower() in self._ini.BOOLEAN_STATES:  # Check inf val is Boolean
                return self._ini.BOOLEAN_STATES[val.lower()]
            else:
                return bool(val)
        else:
            return fallback

    def getint(self, key: str, section: str = None, fallback: Any = None):
        """
        getint.
            Interface for getint function of ini parser
        """
        val = None
        if section is not None:
            try:
                val = self._ini.getint(section, key)
            except Exception:
                pass
        if key in os.environ:
            val = os.getenv(key, fallback)
        if self._redis.exists(key):
            val = self._redis.get(key)
        if not val:
            return fallback
        if val.isdigit():  # Check if val is Integer
            try:
                return int(val)
            except Exception:
                return fallback

    def getlist(self, key: str, section: str = None, fallback: Any = None):
        """
        getlist.
            Get an string and convert to list
        """
        val = None
        if section is not None:
            try:
                val = self._ini.get(section, key)
            except Exception:
                pass
        if key in os.environ:
            val = os.getenv(key, fallback)
        if self._redis.exists(key):
            val = self._redis.get(key)
        if val:
            return val.split(',')
        else:
            return []

    def get(self, key: str, section: str = None, fallback: Any = None) -> Any:
        """
        get.
            Interface for get variable from differents sources
        """
        val = None
        # if not val and if section, get from INI
        if section is not None:
            try:
                val = self._ini.get(section, key)
                return val
            except Exception:
                pass
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)
            return val
        # if not in os.environ, got from Redis
        if self._redis.exists(key):
            return self._redis.get(key)
        # If not in redis, get from MEMCACHED
        if not val:
            val = self._mem.get(key)
            if val:
                return val
        return fallback

    """
    Config Magic Methods (dict like)
    """

    def __setitem__(self, key: str, value: Any) -> None:
        if key in os.environ:
            # override an environment variable
            os.environ[key] = value
        elif self._redis.exists(key):
            self._redis.set(key, value)
        else:
            # saving in memcached:
            self._mem.set(key, value)

    def __getitem__(self, key: str) -> Any:
        """
        Sequence-like operators
        """
        if key in os.environ:
            return os.getenv(key)
        elif self._redis.exists(key):
            return self._redis.get(key)
            # check if exists on memcached
        else:
            val = self._mem.get(key)
            if val:
                return val
            else:
                return None

    def __contains__(self, key: str) -> bool:
        if key in os.environ:
            return True
        if self._redis.exists(key):
            return True
        val = self._mem.get(key)
        if val:
            return True
        else:
            return False

    ## attribute name
    def __getattr__(self, key: str) -> Any:
        if key in os.environ:
            val = os.getenv(key)
        elif self._redis.exists(key):
            val = self._redis.get(key)
        else:
            val = self._mem.get(key)
        if val:
            try:
                if val.lower() in self._ini.BOOLEAN_STATES:
                    return self._ini.BOOLEAN_STATES[val.lower()]
                elif val.isdigit():
                    return int(val)
            finally:
                return val
        else:
            raise TypeError(
                f"NavigatorConfig Error: has not attribute {key}"
            )
        return None

    def set(self, key: str, value: Any) -> None:
        """
        set.
         Set an enviroment variable on REDIS or Memcached, based on Strategy
         TODO: add cloudpickle to serialize and unserialize data.
        """
        return self._redis.set(key, value)

    def setext(self, key: str, value: Any, timeout: int = None) -> int:
        """
        set
            set a variable in redis with expiration
        """
        if not isinstance(timeout, int):
            time = 3600
        else:
            time = timeout
        return self._redis.setex(key, value, time)
