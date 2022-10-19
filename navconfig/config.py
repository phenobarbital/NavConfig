import os
import asyncio
from typing import (
    Any,
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
from navconfig.utils.functions import strtobool
from navconfig.utils.types import Singleton
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

# class Reader(TypedDict):
#     name: str
#     reader: Union[Callable, Awaitable]

class cellarConfig(metaclass=Singleton):
    """
    cellarConfig.
        Universal container for Configuration Management.
    """
    _conffile: str = 'etc/config.ini'
    __initialized__ = False
    _readers: dict = {}
    _mapping_: dict = {}

    def __init__(self, site_root: str = None, env: str = None, create: bool = True, **kwargs):
        if self.__initialized__ is True:
            return
        self.__initialized__ = True
        self._create: bool = create
        self._ini: Callable = None
        # asyncio loop
        self._loop = asyncio.get_event_loop()
        asyncio.set_event_loop(self._loop)
        # this only load at first time
        if not site_root:
            self._site_path = Path(__file__).resolve().parent.parent
        else:
            self._site_path = Path(site_root).resolve()
        # Get External Readers:
        if REDIS_LOADER:
            try:
                self._readers['redis'] = REDIS_LOADER()
            except Exception as err:
                raise Exception(err) from err
        if MEMCACHE_LOADER:
            try:
                self._readers['memcache'] = MEMCACHE_LOADER()
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
        # self._debug = bool(strtobool(os.getenv('DEBUG', 'False')))
        self._debug = bool(self.getboolean('DEBUG', fallback=False))
        # and get the config file declared in the environment file
        config_file = self.get('CONFIG_FILE', fallback=self._conffile)
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
            if self._create is True:
                try:
                    cf.mkdir(parents=True, exist_ok=True)
                except IOError:
                    pass

    def __del__(self):
        try:
            self.close()
        finally:
            pass

    def close(self):
        for _, reader in self._readers.items():
            try:
                reader.close()
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
                override=override,
                create=self._create
            )
            self._mapping_ = self._env_loader.load_environment()
            if self._mapping_ is None:
                self._mapping_ = {} # empty dict
        except (FileExistsError, FileNotFoundError) as ex:
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

    def _get_external(self, key: str) -> Any:
        """Get value fron an External Reader.
        """
        for _, reader in self._readers.items():
            try:
                if reader.exists(key) is True:
                    return reader.get(key)
            except RuntimeError:
                continue
        return None

    def getboolean(self, key: str, section: str = None, fallback: Any = None):
        """
        getboolean.
            Interface for getboolean function of ini parser
        """
        val = None
        # if not val and if section, get from INI
        if section is not None:
            if section in self._mapping_:
                val = self._mapping_[section]
                return strtobool(val)
            elif self._ini:
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
        if key in self._mapping_:
            val = self._mapping_[key]
        elif key in os.environ:
            val = os.getenv(key, fallback)
        else:
            val = self._get_external(key)
        if val:
            return strtobool(val)
        else:
            return fallback

    def getint(self, key: str, section: str = None, fallback: Any = None):
        """
        getint.
            Interface for getint function of ini parser
        """
        val = None
        if section is not None:
            if section in self._mapping_:
                val = self._mapping_[section]
            else:
                try:
                    val = self._ini.getint(section, key)
                except (NoOptionError, NoSectionError):
                    pass
        if key in os.environ:
            val = os.getenv(key, fallback)
        else:
            val = self._get_external(key)
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
            if section in self._mapping_:
                val = self._mapping_[section]
            else:
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

    def getdict(self, key: str) -> dict:
        if key in self._mapping_:
            return self._mapping_[key]
        elif key in os.environ:
            return dict(os.getenv(key))

    def get(self, key: str, section: str = None, fallback: Any = None) -> Any:
        """
        get.
            Interface for get variable from differents sources
        """
        val = None
        # if not val and if section, get from INI
        if section is not None:
            if section in self._mapping_:
                val = self._mapping_[section]
                return val
            elif self._ini:
                try:
                    val = self._ini.get(section, key)
                    return val
                except (NoOptionError, NoSectionError):
                    pass
        if key in self._mapping_:
            return self._mapping_[key]
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)
            return val
        # get data from external readers:
        if val:= self._get_external(key):
            return val
        return fallback

# Config Magic Methods (dict like)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in os.environ:
            # override an environment variable
            os.environ[key] = value
        elif key in self._mapping_:
            return self._mapping_[key]
        else:
            pass # Adding to Mutable Mapping

    def __getitem__(self, key: str) -> Any:
        """
        Sequence-like operators
        """
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        if key in os.environ:
            return True
        elif key in self._mapping_:
            return True
        else:
            for _, reader in self._readers.items():
                val = reader.exists(key)
                if val is True:
                    return True
                else:
                    return False
            return False

    def exists(self, key: str) -> bool:
        if key in os.environ:
            return True
        elif key in self._mapping_:
            return True
        else:
            # get data from external readers:
            val = self._get_external(key)
            if val is not None:
                return True
            return False

    ## attribute name
    def __getattr__(self, key: str) -> Any:
        val = None
        if key in os.environ:
            val = os.getenv(key)
        elif key in self._mapping_:
            val = self._mapping_[key]
        else:
            # get data from external readers:
            val = self._get_external(key)
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

    def set(self, key: str, value: Any) -> None:
        """
        set.
         Set an enviroment variable on REDIS, based on Strategy
         TODO: add cloudpickle to serialize and unserialize data first.
        """
        if REDIS_LOADER:
            return self._readers['redis'].set(key, value)
        return False

    def setext(self, key: str, value: Any, timeout: int = None) -> bool:
        """
        set
            set a variable in redis with expiration
        """
        if REDIS_LOADER:
            if not isinstance(timeout, int):
                time = 3600
            else:
                time = timeout
            return self._readers['redis'].set(key, value, time)
        else:
            return False
