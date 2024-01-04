# Navigator NavConfig #

NavConfig is a configuration tool for getting variables from environment and other sources.
Is used by Navigator Framework, but is possible to use in other applications as well.

NavConfig can load Configuration directives from different sources (can be mixed):

- Environment files (.env)
- pyproject.toml files
- INI files (using configParser)
- TOML/YAML files
- REDIS variables
- Memcached Variables
- Python files (using settings.py)

The main goal of NavConfig is centralize configuration access in a single and
immutable unique point of truth.

NavConfig can be shared across several modules.

## Motivation ##

Any Application requires too many configuration options, some configuration options need to be secrets, credentials, etc, and also, can depend on the environment where the application runs (development, testing, production, etc.).

Instead of creating Python files, we are using python-dotenv + INI files to separate concerns (secrets vs configuration options), NavConfig also supports getting data instead of INI files from YAML or TOML files (for complex types), pyproject.toml files or REDIS variables.

## Installation
```bash
pip install navconfig
```

if you're looking for supporting memcache,redis:

```bash
pip install navconfig[memcache,redis]
```

or adding all features, including logging facility with Logstash Support:

```bash
pip install navconfig[all]
```

## Quickstart ##

First of all, let's create a simple configuration environment.

Creates a directory for an .INI file and the environment (.env) file.

```bash
mkdir {env,etc}
```

put a .env file inside of the "env" folder, the first line is the directive to know where the "INI" file lives (even if we can put the . INI file outside of the current dir).

the directory tree is very simple:

```text
|- myapp/
|  |- __init__.py
|  |- pyproject.toml
|  |- env/
|  |  |- .env
|  |  |- dev/
|  |  |- .env
|  |  |- prod/
|  |  |- .env
|  |- etc/
|  |  |- myconfig.ini
|  | ...
```

```text
# file: .env
CONFIG_FILE=etc/myconfig.ini # CONFIG FILE reference to INI location.
APP_NAME=My App
```

Navconfig exposes a "config" object to retrieve your environment variables inside your application.

```python
from navconfig import config

APP_NAME = config.get('APP_NAME')
# the result is "My App".

```

but also you can use config as a object:

```python
from navconfig import config

APP_NAME = config.APP_NAME
# the result is "My App".

```

## Retrieving values ##

Once an instance of `NavConfig` has been installed, values can be retrieved through:

```python
>>> config.get("APP_NAME")
'My App'
```

there are options available for retrieving values as strings (`get`), integer (`getint()`), booleans (`getboolean()`), but also lists (`getlist()`) and dictionaries (`getdict()`).

An optional second argument can be provided to any `get*` which will be returned as default if
the given config key isn't found:

```python
>>> config.get("APP_NAME", "My App")
'My App'
```

## Configuration directories ##

By default, `NavConfig` will look for configuration files the base path of project, based on the file type:

 * .env files will be searched on a `env/` directory.
 * .yml/.toml files will be searched on `env/` directory.
 * pyproject.toml file will be searched on root of project.
 * .ini files will be searched on `etc/` directory.

## Working with Environments ##

NavConfig can load all environment variables (and the .INI files associated within the .env file) from different directories,
every directory works as a new Environment and you can split your configuration for different environments, like this:

```
env/
.
├── dev
|  |- .env
├── prod
|  |- .env
├── staging
|  |- .env
└── experimental
|  |- .env
```

Then, you can load your application using the "ENV" environment variable:

```bash
ENV=dev python app.py
```


## Configure Logging ##

NavConfig has owns logging facility, if you load logging_config from Navconfig, you will get
a logging configuration using the Python dictConfig format.

also, if you put an environment variable called "logstash_enabled = True", there is a ready to use Logging facility using Logstash.

```python
import logging
from navconfig.logging import (
    logdir,
    loglevel,
    logging_config
)
from logging.config import dictConfig
dictConfig(logging_config)
```

To use just the logger as expected with logging.getLogger(), e.g.

```python
logger = logging.getLogger('MY_APP_NAME')
logger.info('Hello World')
```
By default, the current logging configuration make echo to the standard output:

```bash
[INFO] 2022-03-11 19:31:39,408 navigator: Hello World
```
## Custom Settings ##

with Navconfig, users can create a python module called "settings.py" on package "settings" to create new configuration options and fine-tune their configuration.

```text
|- myapp/
|  |- settings/
|  |- __init__.py
|  |- settings.py
```

on "settings.py", we can create new variables using python code:

```python
from navconfig import config, DEBUG

print('::: LOADING SETTINGS ::: ')

# we are in local aiohttp development?
LOCAL_DEVELOPMENT = (DEBUG is True and sys.argv[0] == 'run.py')
SEND_NOTIFICATIONS = config.get('SEND_NOTIFICATIONS', fallback=True)
```

And those variables are reachable using "navconfig.conf" module:

```python
from navconfig.conf import LOCAL_DEVELOPMENT

if LOCAL_DEVELOPMENT is True:
    print('We are in a Local instance.')

```

## Dependencies ##

 * Python >= 3.9
 * ConfigParser
 * Python-Dotenv
 * pytomlpp
 * PyYAML
 * redis
 * pylibmc

### Contribution guidelines ###

Please have a look at the Contribution Guide

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact

### License ###

NavConfig is released under MIT license.
