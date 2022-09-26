import os
import asyncio
from typing import (
    Any,
    Union
)
from collections.abc import Callable
import logging
from configparser import ConfigParser
from pathlib import Path
from dotenv import load_dotenv
from navconfig.cyphers import FileCypher
from navconfig.utils.functions import Singleton, strtobool
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
        Save remote Environment into a local File.
        """
        env_path = self.site_root.joinpath('env', self.ENV, '.env')
        # pluggable types
        print('ENV ', env_type)
        if env_type == 'drive':
            try:
                from navconfig.loaders import driveLoader # pylint: disable=C0415
                d = driveLoader()
                d.save_enviroment(env_path)
            except Exception as err:
                print('Error Saving Environment', err)

    def load_enviroment(self, env_type: str = 'file', file: Union[str, Path] = None, override: bool = False):
        """
        Load an environment from a File or any pluggable Origin.
        """
        if env_type == 'crypt':
            # TODO: load dynamically
            env_path = self.site_root.joinpath('env', self.ENV)
            logging.debug(f'Environment File: {env_path!s}')
            fc = FileCypher(directory = env_path)
            if not env_path.exists():
                raise FileExistsError(
                    f'No Directory Path: {env_path}'
                )
            try:
                decrypted = asyncio.run(
                    fc.decrypt(name = 'env.crypt')
                )
                load_dotenv(
                    stream=decrypted,
                    override=override
                )
            except FileNotFoundError:
                raise
            except Exception as err:
                print(err)
                raise
        elif env_type == 'file':
            env_path = self.site_root.joinpath('env', self.ENV, '.env')
            logging.debug(
                f'Environment File: {env_path!s}'
            )
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
            # TODO: load dynamically
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
            except Exception:
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
            except Exception:
                pass
        if key in os.environ:
            val = os.getenv(key, fallback)
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
        if self._redis.exists(key) is True:
            return self._redis.get(key)
        return fallback

# Config Magic Methods (dict like)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in os.environ:
            # override an environment variable
            os.environ[key] = value
        else:
            if self._redis.exists(key) is True:
                self._redis.set(key, value)
            else:
                return False

    def __getitem__(self, key: str) -> Any:
        """
        Sequence-like operators
        """
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        if key in os.environ:
            return True
        elif self._redis.exists(key) is True:
            return True
        else:
            return False

    ## attribute name
    def __getattr__(self, key: str) -> Any:
        val = None
        if key in os.environ:
            val = os.getenv(key)
        else:
            if self._redis.exists(key) is True:
                val = self._redis.get(key)
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
         Set an enviroment variable on REDIS, based on Strategy
         TODO: add cloudpickle to serialize and unserialize data first.
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
