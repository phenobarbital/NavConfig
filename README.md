# Navigator NavConfig #

NavConfig is a configuration tool for getting variables from environment and other sources.
Is used by Navigator Framework, but is possible to use in other applications as well.

Navigator NavConfig can load Configuration directives from different sources:

- Environment files (.env)
- Memcached Variables
- INI files (using configParser)
- Redis Server

The main goal of NavConfig is centralize configuration access in a single and
immutable unique point of truth.

NavConfig can be shared across several modules.

## Installation
```bash
pip install navconfig
```

## Quickstart ##

First of all, let's create a simple configuration environment.

Creates a directory for an .ini file and the environment file.

```bash
mkdir {env,etc}
```

put a .env file inside of "env" folder, the first line is the directive to know
where the "ini" file lives (even we can put the .ini file outside of current dir).


```text
CONFIG_FILE=etc/myconfig.ini
APP_NAME=My App
```

Then, in your code, call navconfig "config" object, and start getting your environment variables inside your application.

```python
from navconfig import config

APP_NAME = config.get('APP_NAME')
# the result is "My App".

```

## Dependencies ##

 * ConfigParser
 * Python-Dotenv


### Requirements ###

* Python >= 3.8
* asyncio (https://pypi.python.org/pypi/asyncio/)
* asyncdb
* python-dotenv

### Contribution guidelines ###

Please have a look at the Contribution Guide

* Writing tests
* Code review
* Other guidelines

### Who do I talk to? ###

* Repo owner or admin
* Other community or team contact

### License ###

Navigator is dual-licensed under BSD and Apache 2.0 licenses.
