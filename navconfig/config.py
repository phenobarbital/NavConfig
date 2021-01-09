import os
import importlib
import sys
import types
import logging
from configparser import RawConfigParser, ConfigParser
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
from asyncdb.providers.mcache import mcache
from asyncdb.providers.mredis import mredis


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
        # getting type of enviroment consummer:
        env_type = os.getenv('NAVCONFIG_ENV', 'file') # file by default
        # get the environment
        try:
            self.load_enviroment(env_type)
        except FileNotFoundError:
            logging.error('Environment File Missing, using current env + INI file.')
        # and get the config file declared in the environment file
        config_file = os.getenv('CONFIG_FILE', '/etc/troc/navigator.ini')
        self._ini = ConfigParser()
        #self._ini = RawConfigParser()
        cf = Path(config_file).resolve()
        if not cf.exists():
            cf = site_root.joinpath('etc', self._conffile)
        try:
            #with open(cf) as f:
            self._ini.read(cf)
        except IOError:
            print(cf, "INI file does not exist!")
            raise IOError("INI file does not exist!")
            return None
        # define debug
        self._debug = os.getenv('DEBUG', False)
        # get redis connection
        try:
            redis = {
                "host": os.getenv('CACHEHOST', 'localhost'),
                "port": os.getenv('CACHEPORT', 6379),
                "db": os.getenv('QUERYSET_DB', 0),
            }
            self._redis = mredis(params=redis)
            self._redis.connection()
            if self._debug:
                print("Redis Connected: {}".format(self._redis.is_connected()))
        except Exception as err:
            print(err)
        # get memcache SERVER
        try:
            mem_params = {
                "host": os.getenv('MEMCACHE_HOST', 'localhost'),
                "port": os.getenv('MEMCACHE_PORT', 11211)
            }
            self._mem = mcache(params=mem_params)
            self._mem.connection()
            if self._debug:
                print("Memcache Connected: {}".format(self._mem.is_connected()))
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
            # warning if env_path is an empty file or doesnt exists
            if env_path.exists():
                if os.stat(str(env_path)).st_size == 0:
                    raise FileExistsError('Empty Environment File: {}'.format(env_path))
                # load dotenv
                load_dotenv(dotenv_path=env_path)
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
            load_dotenv(dotenv_path=file)

    def getboolean(self, value, section=None, fallback=None):
        """
        getboolean.
            Interface for getboolean function of ini parser
        """
        val = None
        # get ENV value
        if value in os.environ:
            val = os.getenv(value, fallback)
            if val:
                if val.lower() in self._ini.BOOLEAN_STATES: # Check inf val is Boolean
                    return self._ini.BOOLEAN_STATES[val.lower()]
                else:
                    return bool(val)

        # if not val and if section, get from INI
        if not val and section != None:
            try:
                val = self._ini.getboolean(section, value)
                if not val:
                    return fallback
                else:
                    return bool(val)
            except Exception:
                return fallback

        # If not val and not section, get from MEMCACHED
        if not val and section == None:
             #TODO: change to a non-async MEMCACHED connector
            val = self._mem.get(value)

        # last: check if value exists on ini
        for section in self._ini.sections():
            try:
                val = self._ini.get(section, value)
                if val:
                    if val.lower() in self._ini.BOOLEAN_STATES: # Check inf val is Boolean
                        return self._ini.BOOLEAN_STATES[val.lower()]
            except Exception:
                continue
        return fallback

    def getint(self, value, section=None, fallback=None):
        """
        getint.
            Interface for getint function of ini parser
        """
        val = None
        # get ENV value
        if value in os.environ:
            val = os.getenv(value, fallback)
            if val:
                return int(val)

        # if not val and if section, get from INI
        if not val and section is not None:
            try:
                val = self._ini.getint(section, value)
                if not val:
                    return fallback
                else:
                    return int(val)
            except Exception:
                return fallback

        # If not val and not section, get from MEMCACHED
        if not val and section is None:
            # TODO: change to a non-async MEMCACHED connector
            val = self._mem.get(value)
            if val:
                return int(val)

        # last: check if value exists on ini
        for section in self._ini.sections():
            try:
                val = self._ini.get(section, value)
                if val:
                    if val.isdigit(): # Check if val is Integer
                        return int(val)
            except Exception:
                continue
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
            except Exception:
                pass
        # get ENV value
        if key in os.environ:
            val = os.getenv(key, fallback)
            if val:
                return val
        # if not in os.environ, got from Redis
        if not val and section is None:
            if self._redis.exists(key):
                return self._redis.get(key)
        # If not in redis, get from MEMCACHED
        if not val and section is None:
            val = self._mem.get(key)
            if val:
                return val
        # last: check if value exists on ini
        for section in self._ini.sections():
            try:
                val = self._ini.get(section, key)
                if val:
                    return val
            except Exception:
                continue
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
