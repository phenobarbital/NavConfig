import os
import importlib
import sys
import types
import logging
from configparser import RawConfigParser, ConfigParser
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
import redis
import pylibmc

class mcache(object):
    """
    Basic Connector for Memcached
    """
    args: dict = {
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

    def get(self, key, default = None):
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

    def close(self):
        self._memcached.disconnect_all()


#### TODO: Feature Toggles
class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__new__(cls, *args, **kwargs)
            setattr(cls, '__initialized', True)
        return cls._instances[cls]

class navigatorConfig(metaclass=Singleton):
    """
    navigatorConfig.

        Class for Navigator configuration
    """
    _self = None
    _ini = None
    _mem = None
    _redis = None
    ENV = ''
    _path = '/etc/troc/'
    _conffile = 'navigator.ini'
    _site_path = ''
    _debug = False
    __initialized = False

    def __del__(self):
        if self._mem:
            self._mem.close()

    def __init__(self, site_root=None):
        if(self.__initialized): return
        self.__initialized = True
        # this only load at first time
        if not site_root:
            site_root = Path(__file__).resolve().parent.parent
        self._site_path = site_root
        # get the current environment
        environment = os.getenv('ENV', '')
        self.ENV = environment
        # getting type of enviroment consumer:
        env_type = os.getenv('NAVCONFIG_ENV', 'file') # file by default
        # get the environment
        try:
            logging.debug(f':: Environment type: {env_type}, ENV={environment}')
            self.load_enviroment(env_type)
        except FileNotFoundError:
            logging.error('Environment File Missing, using current env + INI file.')
        # and get the config file declared in the environment file
        config_file = os.getenv('CONFIG_FILE', '/etc/troc/navigator.ini')
        self._ini = ConfigParser()
        #self._ini = RawConfigParser()
        cf = Path(config_file).resolve()
        logging.debug(f':: Config INI File: {cf!s}')
        if not cf.exists():
            cf = site_root.joinpath('etc', self._conffile)
        try:
            #with open(cf) as f:
            self._ini.read(cf)
        except (IOError, Exception) as err:
            print(cf, f"INI file does not exist: {err}")
            raise IOError(f"INI file does not exist: {err}")
            return None
        # define debug
        self._debug = os.getenv('DEBUG', False)
        # get redis connection
        host = os.getenv('CACHEHOST', 'localhost')
        port = os.getenv('CACHEPORT', 6379)
        db = os.getenv('QUERYSET_DB', 0)
        try:
            params = {
                "socket_timeout": 60,
                "encoding": 'utf-8',
                "decode_responses": True
            }
            CACHE_URL = "redis://{}:{}/{}".format(host, port, db)
            self._rpool = redis.ConnectionPool.from_url(url=CACHE_URL, **params)
            self._redis = redis.Redis(connection_pool=self._rpool, **params)
        except Exception as err:
            print(err)
        # get memcache SERVER
        try:
            self._mem = mcache()
        except Exception as err:
            print(err)
            # memcache not working
            self._mem = None

    def save_environment(self, env_type: str = 'drive'):
        env_path = self.site_root.joinpath('env', self.ENV, '.env')
        # pluggable types
        if env_type == 'drive':
            from navconfig.loaders import driveLoader
            try:
                d = driveLoader()
                d.save_enviroment(env_path)
            except Exception as err:
                print('Error Reading Environment from Google Drive', err)

    def load_enviroment(self, env_type: str = 'file'):
        if env_type == 'file':
            env_path = self.site_root.joinpath('env', self.ENV, '.env')
            logging.debug(f'Environment File: {env_path!s}')
            # warning if env_path is an empty file or doesnt exists
            if env_path.exists():
                if os.stat(str(env_path)).st_size == 0:
                    raise FileExistsError('Empty Environment File: {}'.format(env_path))
                # load dotenv
                load_dotenv(dotenv_path=env_path, override=False)
            else:
                raise FileNotFoundError('Environment file not found: {}'.format(env_path))
        else:
            # pluggable types
            if env_type == 'drive':
                from navconfig.loaders import driveLoader
                try:
                    d = driveLoader()
                    d.load_enviroment()
                except Exception as err:
                    print('Error Reading from Google Drive', err)

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
                load_dotenv(dotenv_path=file, override=False)
            except Exception as err:
                raise
        else:
            raise Exception('Failed to load ENV file')

    def getboolean(self, key, section=None, fallback=None):
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
            if val.lower() in self._ini.BOOLEAN_STATES: # Check inf val is Boolean
                return self._ini.BOOLEAN_STATES[val.lower()]
            else:
                return bool(val)
        else:
            return fallback

    def getint(self, key, section=None, fallback=None):
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
        if val.isdigit(): # Check if val is Integer
            try:
                return int(val)
            except Exception:
                return fallback

    def getlist(self, key, section=None, fallback: list = None):
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


    def get(self, key, section=None, fallback=None):
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

    def __getitem__(self, key):
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

    def __contains__(self, key):
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
    def __getattr__(self, key):
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
            # if hasattr(self, key):
            #     return super(navigatorConfig, self).__getattr__(key)
            raise TypeError("NavigatorConfig Error: has not attribute {}".format(key))
        return None

    def set(self, key, value):
        """
        set
            set an enviroment variable on redis
        """
        return self._redis.set(key, value)

    def setext(self, key, value, timeout: int = None):
        """
        set
            set a variable in redis with expiration
        """
        if not isinstance(timeout, int):
            time = 3600
        else:
            time = timeout
        return self._redis.setex(key, time, value)
