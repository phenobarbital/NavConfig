from typing import (
    Any,
    Dict,
    List,
)
import os
import contextlib
import asyncio
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
        self._auto_env: bool = strtobool(os.getenv("AUTO_DISCOVERY", "True"))

        # Core components
        self._site_path: Path = None
        self._env_loader: Callable = None
        self._ini: Callable = None
        self._current_env: str = None
        # Cache for multiple environments
        self._env_cache: Dict[str, Dict] = {}

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
        lazy_load = strtobool(os.getenv('LAZY_LOAD', 'False'))
        if lazy_load is False:
            self.configure(env, **kwargs)

    def configure(
        self,
        env: str = None,
        env_type: str = "vault",
        override: bool = False
    ):
        """
        Configure Kardex with enhanced vault + file loading.

        Args:
            env (str, optional): Environment name (dev, prod, staging).
            env_type (str, optional): Loader type - defaults to "vault" (unified vault+file).
            override (bool, optional): Override current environment variables.

        Raises:
            ConfigError: Error on Configuration.
        """
        # Environment Configuration:
        if env is not None:
            self.ENV = env
            self._current_env = env
        else:
            environment = os.getenv("ENV", "")
            self.ENV = environment
            self._current_env = environment
        # getting type of environment consumer:
        try:
            self.load_environment(
                env_type,
                override=override
            )
        except FileNotFoundError:
            logging.error("NavConfig Error: Environment configuration is missing.")
            # Try fallback to file-only loading
            if env_type == "vault":
                logging.info("Falling back to file-only loading...")
                try:
                    self.load_environment("file", override=override)
                except Exception as err:
                    logging.error(f"Fallback loading also failed: {err}")
                    raise ConfigError(
                        "NavConfig Error: Unable to load environment configuration"
                    ) from err
        # Initialize external readers (redis, memcache, vault as reader)
        self._init_external_readers()
        # Load INI configuration
        self._load_ini_config()
        # Running Load PyProject:
        self.load_pyproject()
        # Defined as initialized:
        self.__initialized__ = True

    def _init_external_readers(self):
        """Initialize external readers (redis, memcache, vault as reader)."""

        # Redis reader
        self._use_redis: bool = strtobool(os.environ.get("USE_REDIS", False))
        if self._use_redis and REDIS_LOADER:
            try:
                self._readers["redis"] = REDIS_LOADER()
            except ReaderNotSet as err:
                logging.error(f"{err}")
                self._use_redis = False
            except Exception as err:
                logging.warning(f"Redis error: {err}")
                raise ConfigError(str(err)) from err

        # Memcache reader
        self._use_memcache: bool = strtobool(os.environ.get("USE_MEMCACHED", False))
        if self._use_memcache and MEMCACHE_LOADER:
            try:
                self._readers["memcache"] = MEMCACHE_LOADER()
            except ReaderNotSet as err:
                logging.error(f"{err}")
                self._use_memcache = False
            except Exception as err:
                raise ConfigError(str(err)) from err

        # Vault as external reader (different from vault loader)
        self._use_vault: bool = strtobool(os.environ.get("VAULT_ENABLED", False))
        if self._use_vault and HVAULT_LOADER:
            try:
                self._readers["vault"] = HVAULT_LOADER(env=self.ENV)
            except ReaderNotSet as err:
                logging.error(f"{err}")
            except Exception as err:
                logging.warning(f"Vault error: {err}")
                raise ConfigError(str(err)) from err

    def _load_ini_config(self):
        """Load INI configuration file."""
        self._debug = bool(self.getboolean("DEBUG", fallback=False))
        config_file = self.get("CONFIG_FILE", fallback=self._conffile)
        self._ini = ConfigParser()

        cf = Path(config_file)
        if not cf.is_absolute():
            cf = self._site_path.joinpath(config_file)
        if not cf.exists():
            cf = self._site_path.joinpath(self._conffile)

        self._ini_path = cf
        if cf.exists():
            try:
                self._ini.read(cf)
            except IOError as err:
                logging.exception(f"NavConfig: INI file doesn't exist: {err}")
            except ParsingError as ex:
                logging.exception(f"Navconfig: unable to parse INI file: {ex}")
        else:
            logging.warning(f"Navconfig: INI file doesn't exists on path: {cf!s}")
            if self._create is True:
                with contextlib.suppress(IOError):
                    cf.parent.mkdir(parents=True, exist_ok=True)

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
            with contextlib.suppress(FileNotFoundError):
                self._pyproject = pyProjectLoader(
                    env_path=project_path,
                    project_name=project_name,
                    project_file=project_file,
                    create=self._create,
                )
                data = self._pyproject.load_environment()
                self._mapping_ = {**self._mapping_, **data}
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

    def load_environment(self, env_type: str = "vault", override: bool = False):
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
                auto=self._auto_env
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
        if not file.exists() or not file.is_file():
            raise ConfigError(
                f"Failed to load a new ENV file from {file}"
            )
        try:
            load_dotenv(dotenv_path=file, override=override)
        except Exception as err:
            raise KardexError(str(err)) from err

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
                    return self._ini.getboolean(section, key)
                except ValueError:
                    val = self._ini.get(section, key)
                    return self._ini.BOOLEAN_STATES[val.lower()] if val else fallback  # noqa
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
        return strtobool(val) if val else fallback

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
                with contextlib.suppress(NoOptionError, NoSectionError):
                    val = self._ini.getint(section, key)
        elif key in os.environ:
            val = os.getenv(key, fallback)
        else:
            val = self._get_external(key)
        if not val:
            return fallback
        try:
            return int(val)
        except (TypeError, ValueError):
            return int(val) if val.isdigit() else fallback

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
                with contextlib.suppress(NoOptionError, NoSectionError):
                    val = self._ini.get(section, key)
        if key in os.environ:
            val = os.getenv(key, fallback)
            val = self._unserialize(val)
        elif key in self._mapping_:
            val = self._mapping_[key]
            if isinstance(val, (list, tuple)):
                return val
        return val.split(",") if val else []

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
                return self._mapping_[section]
            elif self._ini:
                with contextlib.suppress(NoOptionError, NoSectionError):
                    return self._ini.get(section, key)
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
        # Adding to Mutable Mapping

    def __getitem__(self, key: str) -> Any:
        """
        Sequence-like operators
        """
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        if key in os.environ or key in self._mapping_:
            return True
        else:
            for _, reader in self._readers.items():
                val = reader.exists(key)
                return val is True
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
            time = timeout if isinstance(timeout, int) else 3600
            try:
                return self._readers["redis"].set(key, value, time)
            except KeyError:
                logging.warning(f"Unable to Set key {key} in Redis")
        elif vault:
            time = timeout if isinstance(timeout, int) else 3600
            try:
                return self._readers["vault"].set(key, value, timeout=timeout)
            except (ValueError, AttributeError):
                logging.warning(
                    f"Unable to Set key {key} in Vault"
                )
        else:
            return False

    def set_env(self, new_env: str, reload: bool = True) -> bool:
        """
        Switch environment at runtime.

        Args:
            new_env: Target environment (dev, prod, staging, etc.)
            reload: Whether to reload configuration immediately

        Returns:
            bool: True if switch was successful
        """
        if new_env == self._current_env:
            logging.debug(f"Already in environment: {new_env}")
            return True

        old_env = self._current_env

        try:
            # Check cache first
            if new_env in self._env_cache and not reload:
                self._mapping_ = self._env_cache[new_env].copy()
                self._current_env = new_env
                self.ENV = new_env
                logging.info(f"Switched to cached environment: {new_env}")
                return True

            # Switch environment in loader if supported
            if hasattr(self._env_loader, 'set_environment'):
                self._env_loader.set_environment(new_env)
                self._current_env = new_env
                self.ENV = new_env
            else:
                # Reinitialize loader for new environment
                self._current_env = new_env
                self.ENV = new_env
                self.load_environment(override=False)

            logging.info(f"Environment switched from {old_env} to {new_env}")
            return True

        except Exception as e:
            # Rollback on error
            self._current_env = old_env
            self.ENV = old_env
            logging.error(f"Failed to switch to environment {new_env}: {e}")
            raise RuntimeError(f"Environment switch failed: {e}") from e

    def get_current_env(self) -> str:
        """Get currently active environment."""
        return self._current_env

    def list_available_envs(self) -> List[str]:
        """List all available environments from filesystem."""
        envs = set()

        try:
            env_base = self.site_root / "env"
            if env_base.exists():
                envs.update(d.name for d in env_base.iterdir() if d.is_dir())
        except Exception as e:
            logging.debug(f"Error scanning filesystem environments: {e}")

        # Add any cached environments
        envs.update(self._env_cache.keys())

        return sorted(envs)

    def get_env_info(self) -> Dict[str, Any]:
        """Get comprehensive information about current environment."""
        info = {
            'current_env': self._current_env,
            'loader_type': type(self._env_loader).__name__ if self._env_loader else None,
            'available_envs': self.list_available_envs(),
            'cached_envs': list(self._env_cache.keys()),
            'site_root': str(self.site_root),
            'total_variables': len(self._mapping_),
        }

        # Add vault-specific information if available
        if hasattr(self._env_loader, 'get_vault_status'):
            info['vault_status'] = self._env_loader.get_vault_status()

        # Add file loading information if available
        if hasattr(self._env_loader, 'get_loaded_files'):
            loaded_files = self._env_loader.get_loaded_files()
            info['loaded_files'] = [str(f) for f in loaded_files]
            info['file_count'] = len(loaded_files)

        return info

    def get_with_env(self, key: str, env: str = None, fallback: Any = None) -> Any:
        """
        Get a variable from a specific environment without switching.

        Usage:
            prod_db = config.get_with_env('DATABASE_URL', 'prod')
        """
        if env is None or env == self._current_env:
            return self.get(key, fallback=fallback)

        # Check cache first
        if env in self._env_cache:
            return self._env_cache[env].get(key, fallback)

        # Load environment temporarily (simplified version)
        try:
            temp_env_path = self.site_root.joinpath("env", env)
            if temp_env_path.exists():
                from .loaders.vault import vaultLoader
                temp_loader = vaultLoader(
                    env_path=temp_env_path,
                    env=env,
                    override=False,
                    create=False,
                )
                if temp_data := temp_loader.load_environment():
                    # Cache for future use
                    self._env_cache[env] = temp_data.copy()
                    return temp_data.get(key, fallback)

        except Exception as e:
            logging.debug(f"Failed to load environment {env}: {e}")

        return fallback

    def clear_env_cache(self, env: str = None):
        """Clear cached environment data."""
        if env:
            self._env_cache.pop(env, None)
            logging.debug(f"Cleared cache for environment: {env}")
        else:
            self._env_cache.clear()
            logging.debug("Cleared all environment cache")

    def reload_current_env(self):
        """Reload current environment from source."""
        self.set_env(self._current_env, reload=True)
