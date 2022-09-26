import os
import asyncio
from typing import (
    Any
)
from collections.abc import Callable
import logging
from configparser import (
    ConfigParser,
    ParsingError,
    NoOptionError,
    NoSectionError
)
from pathlib import Path
from dotenv import load_dotenv
from navconfig.utils.functions import Singleton, strtobool
from navconfig.loaders import import_loader
## memcache
try:
    from .readers.memcache import mcache
    MEMCACHE_LOADER=mcache
except ModuleNotFoundError:
    MEMCACHE_LOADER=None
## redis:
try:
    from .readers.redis import mredis
    REDIS_LOADER=mredis
except ModuleNotFoundError:
    REDIS_LOADER=None


class navigatorConfig(metaclass=Singleton):
    """
    navigatorConfig.
        Class for Application configuration.
    """
    _redis: Callable = None
    _conffile: str = 'etc/config.ini'
    __initialized = False

    def __init__(self, site_root: str = None, env: str = None, **kwargs):
        if self.__initialized is True:
            return
        self.__initialized = True
        # asyncio loop
        self._loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self._loop)
        # this only load at first time
        if not site_root:
            self._site_path = Path(__file__).resolve().parent.parent
        else:
            self._site_path = Path(site_root).resolve()
        print('SITE PATH ', self._site_path)
        # get redis connection (only if enabled)
        if REDIS_LOADER:
            try:
                self._redis = REDIS_LOADER()
            except Exception as err:
                raise Exception(err) from err
        if MEMCACHE_LOADER:
            try:
                self._mcache = MEMCACHE_LOADER()
            except Exception as err:
                raise Exception(err) from err
        # then: configure the instance:
        self.configure(env, **kwargs)

    def configure(
            self,
            env: str = None,
            env_type: str = 'file',
            override: bool = False
        ):
        # Environment Configuration:
        if env is not None:
            self.ENV = env
        else:
            environment = os.getenv('ENV', '')
            self.ENV = environment
        # getting type of enviroment consumer:
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
            cf = self._site_path.joinpath(self._conffile)
        if cf.exists():
            try:
                self._ini.read(cf)
            except IOError as err:
                logging.exception(
                    f"NavConfig: INI file doesn't exist: {err}"
                )
            except ParsingError as ex:
                logging.exception(
                    f"Navconfig: unable to parse INI file: {ex}"
                )
        else:
            logging.warning(
                f"Navconfig: INI file doesn't exists on path: {cf!s}"
            )

    def __del__(self):
        try:
            self.close()
        finally:
            pass

    def close(self):
        try:
            if REDIS_LOADER:
                self._redis.close()
            if MEMCACHE_LOADER:
                self._mcache.close()
        except Exception as err: # pylint: disable=W0703
            logging.error(err)

    @property
    def debug(self):
        return self._debug

    def save_environment(self, env_type: str = 'drive'):
        """
        Saving a remote Environment into a local File.
        """
        env_path = self.site_root.joinpath('env', self.ENV, '.env')
        # pluggable types
        print('ENV ', env_type)
        if self._env_loader.downloadable is True:
            self._env_loader.save_enviroment(env_path)

    def load_enviroment(self, env_type: str = 'file', override: bool = False):
        """load_environment.
            Load an environment from a File or any pluggable Origin.
        """
        try:
            env_path = self.site_root.joinpath('env', self.ENV)
            logging.debug(f'Environment Path: {env_path!s}')
            obj = import_loader(loader=env_type)
            self._env_loader = obj(
                env_path=env_path,
                env_file='',
                override=override
            )
            self._env_loader.load_environment()
        except FileNotFoundError as ex:
            logging.warning(ex)
            raise
        except RuntimeError as ex:
            raise RuntimeError(
                ex
            ) from ex
        except Exception as ex:
            logging.exception(ex, stack_info=True)
            raise RuntimeError(
                f"Navconfig: Exception on Env loader: {ex}"
            ) from ex

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
                raise Exception(err) from err
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
            except (NoOptionError, NoSectionError):
                return fallback
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)

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
            except (NoOptionError, NoSectionError):
                pass
        if key in os.environ:
            val = os.getenv(key, fallback)
        if not val:
            return fallback
        if val.isdigit():  # Check if val is Integer
            try:
                return int(val)
            except (TypeError, ValueError):
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
            except (NoOptionError, NoSectionError):
                pass
        if key in os.environ:
            val = os.getenv(key, fallback)
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
            except (NoOptionError, NoSectionError):
                pass
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)
            return val
        # if not in os.environ, got from Redis
        if REDIS_LOADER:
            if self._redis.exists(key) is True:
                return self._redis.get(key)
        return fallback

# Config Magic Methods (dict like)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in os.environ:
            # override an environment variable
            os.environ[key] = value
        else:
            if REDIS_LOADER:
                if self._redis.exists(key) is True:
                    self._redis.set(key, value)

    def __getitem__(self, key: str) -> Any:
        """
        Sequence-like operators
        """
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        if key in os.environ:
            return True
        else:
            if REDIS_LOADER:
                if self._redis.exists(key) is True:
                    return True
                else:
                    return False
            else:
                return False

    ## attribute name
    def __getattr__(self, key: str) -> Any:
        val = None
        if key in os.environ:
            val = os.getenv(key)
        else:
            if REDIS_LOADER:
                if self._redis.exists(key) is True:
                    val = self._redis.get(key)
        if val:
            try:
                if val.lower() in self._ini.BOOLEAN_STATES:
                    return self._ini.BOOLEAN_STATES[val.lower()]
                elif val.isdigit():
                    return int(val)
            finally:
                return val # pylint: disable=W0150
        else:
            raise TypeError(
                f"NavigatorConfig Error: has not attribute {key}"
            )
        return None

    def set(self, key: str, value: Any) -> None:
        """
        set.
         Set an enviroment variable on REDIS, based on Strategy
         TODO: add cloudpickle to serialize and unserialize data first.
        """
        if REDIS_LOADER:
            return self._redis.set(key, value)
        return False

    def setext(self, key: str, value: Any, timeout: int = None) -> int:
        """
        set
            set a variable in redis with expiration
        """
        if REDIS_LOADER:
            if not isinstance(timeout, int):
                time = 3600
            else:
                time = timeout
            return self._redis.setex(key, value, time)
        return False
