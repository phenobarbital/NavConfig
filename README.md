# NavConfig

NavConfig is a configuration management library for Python projects. It is
the default configuration layer of the Navigator Framework, but it works
perfectly as a stand-alone tool for any Python application.

NavConfig can load configuration directives from multiple sources (and
combine them):

- Environment files (`.env`)
- INI files (via `configparser`)
- TOML and YAML files
- `pyproject.toml`
- Redis
- Memcached
- HashiCorp Vault
- Python settings modules (`settings/settings.py`)

The main goal of NavConfig is to centralize configuration access through a
single, immutable point of truth that can be shared across modules.


## Motivation

Applications require many configuration options. Some of those options hold
secrets or credentials and must be kept separate from general settings.
Configuration also varies between environments (development, staging,
production).

NavConfig addresses this by loading secrets from `.env` files and structured
settings from INI/TOML/YAML files, keeping concerns separated. It also
supports retrieving configuration from external stores such as Redis,
Memcached, or HashiCorp Vault.


## Installation

```bash
pip install navconfig
```

To include optional backends:

```bash
# Redis and Memcached support
pip install navconfig[redis,memcache]

# All features, including Logstash logging
pip install navconfig[all]
```


## Quickstart

### Bootstrapping a new project with `kardex`

NavConfig ships a small CLI called `kardex` that creates the directory layout
your project needs.

```bash
kardex create --env dev
```

This command generates the following structure in the current directory:

```text
.
|-- env/
|   +-- dev/
|       +-- .env
|-- etc/
|   +-- config.ini
+-- logs/
```

- `env/dev/.env` -- environment variables (secrets, feature flags, paths).
- `etc/config.ini` -- INI-based settings consumed by NavConfig, including a
  `[logging]` section.
- `logs/` -- default directory where rotating log files are written.

The generated files come from the bundled samples in
`navconfig/samples/`. You can inspect or customize those samples before
running `kardex create`.

Use `--path` to point to a different project root:

```bash
kardex create --env dev --path /srv/myapp
```

### Creating additional environments

Once the base structure exists you can add more environments:

```bash
kardex new-env prod
```

This copies `env/.env` (or the bundled sample if no base file exists) into
`env/prod/.env`, adjusting the `ENV` variable automatically.

To include HashiCorp Vault connection variables in the new environment, pass
`--vault`:

```bash
kardex new-env staging --vault
```

The generated `.env` will contain extra variables such as `VAULT_ADDR`,
`VAULT_TOKEN`, `VAULT_MOUNT_POINT`, and others that NavConfig can use when
`ENV_TYPE=vault`.

### Directory layout

A typical project looks like this:

```text
myapp/
|-- __init__.py
|-- pyproject.toml
|-- env/
|   |-- .env          (optional base file)
|   |-- dev/
|   |   +-- .env
|   |-- staging/
|   |   +-- .env
|   +-- prod/
|       +-- .env
|-- etc/
|   +-- config.ini
|-- logs/
+-- settings/
    |-- __init__.py
    +-- settings.py   (optional)
```

### Selecting an environment

Set the `ENV` variable before starting your application:

```bash
ENV=prod python app.py
```

NavConfig will load `env/prod/.env` and any INI file referenced by its
`CONFIG_FILE` directive.

### Accessing configuration

```python
from navconfig import config

APP_NAME = config.get("APP_NAME")
# "MyApp"
```

Attribute-style access also works:

```python
APP_NAME = config.APP_NAME
```

### Typed accessors

```python
config.get("APP_NAME")                  # str
config.getint("PORT", fallback=8080)    # int
config.getboolean("DEBUG")             # bool
config.getlist("ALLOWED_HOSTS")        # list (comma-separated)
config.getdict("EXTRA")               # dict
```

An optional `fallback` argument is returned when the key is not found:

```python
config.get("MISSING_KEY", "default_value")
```


## Configuration directories

By default NavConfig looks for files relative to the project root:

| File type            | Default location            |
| -------------------- | --------------------------- |
| `.env`               | `env/` (plus ENV subdirectory) |
| `.yml` / `.toml`     | `env/`                      |
| `pyproject.toml`     | project root                |
| `.ini`               | `etc/`                      |


## Configure logging

NavConfig provides a ready-to-use logging facility. Import `logging_config`
and apply it with `dictConfig`:

```python
import logging
from navconfig.logging import logdir, loglevel, logging_config
from logging.config import dictConfig

dictConfig(logging_config)
```

Then use `logging.getLogger()` as usual:

```python
logger = logging.getLogger("MY_APP")
logger.info("Hello World")
```

Console output uses colored formatting by default:

```
[INFO] 2024-03-11 19:31:39,408 MY_APP: Hello World
```

Logging behaviour is controlled by the `[logging]` section in your INI file.
The bundled `config.ini.sample` includes all available options.


## Custom settings module

You can create a Python package called `settings` in your project to define
additional configuration derived from NavConfig values:

```text
myapp/
+-- settings/
    |-- __init__.py
    +-- settings.py
```

Inside `settings/settings.py`:

```python
import sys
from navconfig import config, DEBUG

LOCAL_DEVELOPMENT = DEBUG is True and sys.argv[0] == "run.py"
SEND_NOTIFICATIONS = config.get("SEND_NOTIFICATIONS", fallback=True)
```

Variables defined there are accessible through `navconfig.conf`:

```python
from navconfig.conf import LOCAL_DEVELOPMENT

if LOCAL_DEVELOPMENT:
    print("Running in local development mode.")
```


## Dependencies

- Python >= 3.10
- python-dotenv
- configparser
- PyYAML
- pytomlpp
- orjson
- cryptography / pycryptodomex
- hvac (HashiCorp Vault client)

Optional: `redis`, `pylibmc` / `aiomcache`, `python-logstash-async`,
`uvloop`.


## Contribution guidelines

Please see the Contribution Guide for details on:

- Writing tests
- Code review process
- Other guidelines


## License

NavConfig is released under the MIT License.
