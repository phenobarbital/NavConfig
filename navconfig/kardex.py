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
import jsonpickle
from .utils.functions import strtobool
from .utils.types import Singleton
from .loaders import import_loader, pyProjectLoader
from .exceptions import ConfigError, KardexError, ReaderNotSet


## memcache:
try:
    from .readers.memcache import mcache

    MEMCACHE_LOADER = mcache
except ModuleNotFoundError:
    MEMCACHE_LOADER = None
## redis:
try:
    from .readers.redis import mredis

    REDIS_LOADER = mredis
except ModuleNotFoundError:
    REDIS_LOADER = None

## Hashicorp Vault:
try:
    from .readers.vault import VaultReader

    HVAULT_LOADER = VaultReader
except ModuleNotFoundError:
    HVAULT_LOADER = None


class Kardex(metaclass=Singleton):
    """
    Kardex.
        Universal container for Configuration Management.
    """

    _conffile: str = "etc/config.ini"
    __initialized__ = False
    _readers: dict = {}
    _mapping_: dict = {}

    def __init__(
        self,
        site_root: str = None,
        env: str = None,
        **kwargs
    ):
        if self.__initialized__ is True:
            return

        # check if create is True (default: false)
        # create the required directories:
        self._create: bool = strtobool(os.getenv("CONFIG_CREATE", False))
        self._ini: Callable = None
        lazy_load = strtobool(os.getenv('LAZY_LOAD', 'False'))
        # asyncio loop
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        # this only load at first time
        if not site_root:
            # TODO: better discovery of Project Root
            self._site_path = Path(__file__).resolve().parent.parent
        else:
            if isinstance(site_root, str):
                self._site_path = Path(site_root).resolve()
            else:
                self._site_path = site_root
        # then: configure the instance:
        if lazy_load is False:
            self.configure(env, **kwargs)

    def configure(
        self,
        env: str = None,
        env_type: str = "file",
        override: bool = False
    ):
        """_summary_

        Args:
            env (str, optional): Environment name (dev, prod).
              Defaults to None.
            env_type (str, optional): type of enviroment.
              Defaults to "file".
            override (bool, optional): override current .env variables.
              Defaults to False.

        Raises:
            ConfigError: Error on Configuration.
        """
        # Environment Configuration:
        if env is not None:
            self.ENV = env
        else:
            environment = os.getenv("ENV", "")
            self.ENV = environment
        # getting type of enviroment consumer:
        try:
            self.load_enviroment(
                env_type,
                override=override
            )
        except FileNotFoundError:
            logging.error(
                "NavConfig Error: Environment (.env) File is Missing."
            )
        # Get External Readers:
        self._use_redis: bool = strtobool(os.environ.get("USE_REDIS", False))
        if self._use_redis:
            if REDIS_LOADER:
                try:
                    self._readers["redis"] = REDIS_LOADER()
                except ReaderNotSet as err:
                    logging.error(f"{err}")
                    self._use_redis = False
                except Exception as err:
                    logging.warning(f"Redis error: {err}")
                    raise ConfigError(str(err)) from err
        self._use_memcache: bool = strtobool(
            os.environ.get("USE_MEMCACHED", False)
        )
        if self._use_memcache:
            if MEMCACHE_LOADER:
                try:
                    self._readers["memcache"] = MEMCACHE_LOADER()
                except ReaderNotSet as err:
                    logging.error(f"{err}")
                    self._use_memcache = False
                except Exception as err:
                    raise ConfigError(str(err)) from err
        ## Hashicorp Vault:
        self._use_vault: bool = strtobool(os.environ.get("USE_VAULT", False))
        if self._use_vault:
            if HVAULT_LOADER:
                try:
                    self._readers["vault"] = HVAULT_LOADER(
                        env=self.ENV
                    )
                except ReaderNotSet as err:
                    logging.error(f"{err}")
                except Exception as err:
                    logging.warning(f"Vault error: {err}")
                    raise ConfigError(str(err)) from err
        # define debug
        self._debug = bool(self.getboolean("DEBUG", fallback=False))
        # and get the config file declared in the environment file
        config_file = self.get("CONFIG_FILE", fallback=self._conffile)
        self._ini = ConfigParser()
        cf = Path(config_file)
        if not cf.is_absolute():
            cf = self._site_path.joinpath(config_file)
        if not cf.exists():
            # try ini file from etc/ directory.
            cf = self._site_path.joinpath(self._conffile)
        self._ini_path = cf
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
        # Running Load PyProject:
        self.load_pyproject()
        # Defined as initialized:
        self.__initialized__ = True

    @property
    def initialized(self) -> bool:
        return self.__initialized__

    def __del__(self):
        try:
            self.close()
        finally:
            pass

    def close(self):
        for _, reader in self._readers.items():
            try:
                reader.close()
            except Exception as err:  # pylint: disable=W0703
                logging.error(f"NavConfig: Error on Reader close: {err}")

    @property
    def debug(self):
        return self._debug

    def load_pyproject(self):
        """
        Load a pyproject.toml file and set the configuration
        """
        try:
            project_name = os.getenv("PROJECT_NAME", "navconfig")
            project_path = os.getenv("PROJECT_PATH", self.site_root)
            project_file = os.getenv("PROJECT_FILE", "pyproject.toml")
            if isinstance(project_path, str):
                project_path = Path(project_path).resolve()
            try:
                self._pyproject = pyProjectLoader(
                    env_path=project_path,
                    project_name=project_name,
                    project_file=project_file,
                    create=self._create,
                )
                data = self._pyproject.load_environment()
                self._mapping_ = {**self._mapping_, **data}
            except FileNotFoundError:
                # don't raise an error if file doesn't exist
                pass
        except Exception as err:
            logging.exception(err)
            raise ConfigError(
                f"PyProject: {err}"
            ) from err

    def save_environment(self, env_type: str = "drive"):
        """
        Saving a remote Environment into a local File.
        """
        env_path = self.site_root.joinpath("env", self.ENV, ".env")
        # pluggable types
        if self._env_loader.downloadable is True:
            self._env_loader.save_enviroment(env_path)

    def load_enviroment(self, env_type: str = "file", override: bool = False):
        """load_environment.
        Load an environment from a File or any pluggable Origin.
        """
        try:
            env_path = self.site_root.joinpath("env", self.ENV)
            logging.debug(
                f"Environment Path: {env_path!s}"
            )
            obj = import_loader(loader=env_type)
            self._env_loader = obj(
                env_path=env_path,
                env_file="",
                override=override,
                create=self._create,
                env=self.ENV,
            )
            self._mapping_ = self._env_loader.load_environment()
            if self._mapping_ is None:
                self._mapping_ = {}  # empty dict
        except (FileExistsError, FileNotFoundError) as ex:
            logging.warning(str(ex))
            raise
        except RuntimeError as ex:
            raise RuntimeError(str(ex)) from ex
        except Exception as ex:
            logging.exception(ex, stack_info=True)
            raise RuntimeError(
                f"Navconfig: Exception on Env loader: {ex}"
            ) from ex

    def source(self, option: str = "ini") -> object:
        """
        source.
            Return a configuration source.
        """
        if option == "ini":
            return self._ini
        elif option == "env":
            return self._env_loader
        elif option in self._readers:
            return self._readers[option]
        else:
            return None

    @property
    def site_root(self):
        return self._site_path

    @property
    def ini_path(self):
        return self._ini_path

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

    def addEnv(self, file, override: bool = False):
        """
        Add a new ENV file to the current environment.

        Args:
            file (Path): File to be loaded on ENV
            override (bool, optional): Override current ENV variables.
              Defaults to False.
        """
        if file.exists() and file.is_file():
            try:
                load_dotenv(dotenv_path=file, override=override)
            except Exception as err:
                raise KardexError(str(err)) from err
        else:
            raise ConfigError(
                f"Failed to load a new ENV file from {file}"
            )

    def _get_external(self, key: str) -> Any:
        """Get value fron an External Reader."""
        for _, reader in self._readers.items():
            try:
                if reader.enabled is True and reader.exists(key) is True:
                    return reader.get(key)
            except RuntimeError:
                continue
        return None

    def section(self, section: str) -> dict:
        """
        section.
            Return a section from the INI parser
        """
        try:
            return dict(self._ini[section])
        except KeyError:
            return {}

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
            val = self._unserialize(val)
        else:
            val = self._get_external(key)
            val = self._unserialize(val)
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
        elif key in os.environ:
            val = os.getenv(key, fallback)
        else:
            val = self._get_external(key)
        if not val:
            return fallback
        try:
            return int(val)
        except (TypeError, ValueError):
            if val.isdigit():
                return int(val)
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
            val = self._unserialize(val)
        elif key in self._mapping_:
            val = self._mapping_[key]
            if isinstance(val, (list, tuple)):
                return val
        if val:
            return val.split(",")
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
            val = self._unserialize(val)
            return val
        # get data from external readers:
        if val := self._get_external(key):
            val = self._unserialize(val)
            return val
        return fallback

    # Config Magic Methods (dict like)
    def __setitem__(self, key: str, value: Any) -> None:
        if key in os.environ:
            # override an environment variable
            value = self._serialize(value)
            os.environ[key] = value
        elif key in self._mapping_:
            return self._mapping_[key]
        else:
            pass  # Adding to Mutable Mapping

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
            val = self._unserialize(val)
            try:
                if val.lower() in self._ini.BOOLEAN_STATES:
                    return self._ini.BOOLEAN_STATES[val.lower()]
                elif val.isdigit():
                    return int(val)
            finally:
                return val  # pylint: disable=W0150
        else:
            raise AttributeError(
                f"Config Error: has not attribute {key}"
            )

    def _serialize(self, value: Any) -> Any:
        # Check if serialization is needed
        if not isinstance(value, (str, int, float, bool)):
            val = jsonpickle.encode(value)
            value = 'NAVCONFIG_JSONDATA:' + val
        return value

    def _unserialize(self, value: Any) -> str:
        if value and str(value).startswith("NAVCONFIG_JSONDATA"):
            try:
                return jsonpickle.decode(
                    value[len("NAVCONFIG_JSONDATA:"):]
                )
            except jsonpickle.UnpicklingError:
                # Fallback to the original string if deserialization fails
                pass
        return value

    def set(self, key: str, value: Any) -> None:
        """
        set.
         Set an enviroment variable on REDIS, based on Strategy
         TODO: add cloudpickle to serialize and unserialize data first.
        """
        if key in self._mapping_:
            self._mapping_[key] = value
        elif key in os.environ:
            os.environ[key] = value
        elif self._use_vault is True:
            try:
                return self._readers["vault"].set(key, value)
            except KeyError:
                logging.warning(
                    f"Unable to Set key {key} in Vault"
                )
            except Exception:
                raise
        elif self._use_redis:
            value = self._serialize(value)
            try:
                return self._readers["redis"].set(key, value)
            except KeyError:
                logging.warning(
                    f"Unable to Set key {key} in Redis"
                )
        else:
            # set the mapping:
            self._mapping_[key] = value
            value = self._serialize(value)
            # Fallback: set in the environment:
            os.environ[key] = value
        return False

    def setext(
        self, key: str, value: Any, timeout: int = None, vault: bool = False
    ) -> bool:
        """
        set
            set a variable in redis with expiration
        """
        if self._use_redis:
            if not isinstance(timeout, int):
                time = 3600
            else:
                time = timeout
            try:
                return self._readers["redis"].set(key, value, time)
            except KeyError:
                logging.warning(f"Unable to Set key {key} in Redis")
        elif vault is True:
            if not isinstance(timeout, int):
                time = 3600
            else:
                time = timeout
            try:
                return self._readers["vault"].set(key, value, timeout=timeout)
            except (ValueError, AttributeError):
                logging.warning(
                    f"Unable to Set key {key} in Vault"
                )
        else:
            return False
