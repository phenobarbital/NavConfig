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
- HashiCorp Vault
- Python settings modules (`settings/settings.py`)

The main goal of NavConfig is to centralize configuration access through a
single, immutable point of truth that can be shared across modules.

Documentation: <https://phenobarbital.github.io/navconfig/>


## Motivation

Applications require many configuration options. Some of those options hold
secrets or credentials and must be kept separate from general settings.
Configuration also varies between environments (development, staging,
production).

NavConfig addresses this by loading secrets from `.env` files and structured
settings from INI/TOML/YAML files, keeping concerns separated. It also
supports retrieving configuration from external stores such as Redis
or HashiCorp Vault.


## Installation

```bash
pip install navconfig
```

To include optional backends:

```bash
# Redis support
pip install navconfig[redis]

# HashiCorp Vault support
pip install navconfig[hvac]

# Logstash logging
pip install navconfig[logstash]

# All features
pip install navconfig[all]
```


## The `kardex` CLI

NavConfig ships a command line tool called `kardex` that bootstraps and
maintains the configuration layout of a project. It is organised in
command groups, each with its own actions:

| Command | What it does |
| ------- | ------------ |
| `kardex env create` | Create the default project structure. |
| `kardex env create --split` | Same, plus the supplementary `.env.*` files. |
| `kardex env new <name>` | Add an environment from the shared `env/.env`. |
| `kardex vault create` | Write the HashiCorp Vault directives into `env/<env>/.env`. |
| `kardex vault migrate` | Push the variables of an environment into Vault. |
| `kardex vault save VAR:VALUE` | Store one or more variables in Vault. |
| `kardex log enable` | Enable the `[logging]` section of `etc/config.ini`. |

Run `kardex <group> <action> --help` for the full list of options.

> **Upgrading from 2.x:** `kardex create` and `kardex new-env` were removed
> in 3.0. Use `kardex env create` and `kardex env new` instead.


## Quickstart

### 1. Create the project structure

```bash
kardex env create --env dev
```

This generates the following structure in the current directory:

```text
.
|-- env/
|   |-- .env          (shared across environments, no ENV= pin)
|   +-- dev/
|       +-- .env      (pinned to ENV=dev)
|-- etc/
|   +-- config.ini
|-- logs/
+-- templates/
```

- `env/.env` -- values shared by every environment. `kardex env new` uses it
  as the template for new environments.
- `env/dev/.env` -- environment variables (secrets, feature flags, paths).
- `etc/config.ini` -- INI-based settings consumed by NavConfig, including a
  `[logging]` section.
- `logs/` -- default directory where rotating log files are written.
- `templates/` -- default directory for template files.

Existing files are never overwritten; pass `--force` when you do want them
replaced. Use `--path` to point at a different project root:

```bash
kardex env create --env dev --path /srv/myapp
```

### 2. Split the configuration across several files (optional)

NavConfig loads `.env` first and then a set of supplementary files, which
keeps unrelated concerns apart. Pass `--split` to create them all:

```bash
kardex env create --env dev --split
```

```text
env/dev/
|-- .env             base configuration and Vault credentials
|-- .env.resources   paths and resource-level directives
|-- .env.databases   database connection settings
|-- .env.api         HTTP layer settings
|-- .env.cache       Redis / cache backend settings
+-- .env.local       local overrides, loaded last (keep out of git)
```

Files are loaded in that order, so `.env.local` always wins. Everything ends
up in the same flat namespace, so `config.get("DBHOST")` works regardless of
which file declared it.

### 3. Add more environments

```bash
kardex env new prod
kardex env new staging --split
```

This copies `env/.env` (or the bundled sample if no shared file exists) into
`env/<name>/.env`, adjusting the `ENV` variable automatically.

### 4. Select an environment

Set the `ENV` variable before starting your application:

```bash
ENV=prod python app.py
```

NavConfig loads `env/prod/.env` and any INI file referenced by its
`CONFIG_FILE` directive.


## HashiCorp Vault

### Configure the connection

```bash
kardex vault create --env dev \
    --url http://vault.internal:8200 \
    --token "$VAULT_TOKEN" \
    --mount-point myapp
```

This appends a delimited block to `env/dev/.env` (creating the file if it
does not exist yet) with the directives NavConfig reads:

```ini
VAULT_ENABLED=true
VAULT_URL=http://vault.internal:8200
VAULT_TOKEN=...
VAULT_MOUNT_POINT=myapp
VAULT_VERSION=2
# VAULT_ENV=
```

Secrets are then read from `<VAULT_MOUNT_POINT>/<ENV>/`, and merged on top
of the file-based values. Set `VAULT_ENV` to read from a different path
segment than `ENV`; set `NAVCONFIG_FILE_OVERRIDE_ENABLED=true` to let the
`.env` files win over Vault instead.

Re-running the command updates only the directives you pass on the command
line, which makes token rotation a one-liner. Pass `--force` to rewrite the
whole block.

### Migrate an existing `.env` into Vault

```bash
kardex vault migrate --env dev --dry-run   # inspect first
kardex vault migrate --env dev
```

Two families of variables are deliberately left in the `.env` file, because
NavConfig needs them before it can reach Vault:

- the Vault directives themselves (`VAULT_*`), and
- the bootstrap directives (`ENV`, `CONFIG_FILE`, `SITE_ROOT`, ...), which
  can be included anyway with `--include-bootstrap`.

Useful options: `--include-extra` (also migrate the `.env.*` files),
`--keep-existing` (never overwrite a key already stored in Vault), `--file`
(migrate an arbitrary file) and `--yes` (skip the confirmation prompt).

Values are masked in the output, and nothing is written until you confirm.

### Store single variables

```bash
kardex vault save DB_PASSWORD:s3cr3t
kardex vault save "DSN:postgres://user:pass@host:5432/db" API_KEY:abc123
```

Only the first colon separates the name from the value, so values may
contain colons themselves.


## Logging

Enable the logging facility with:

```bash
kardex log enable
```

That writes the `[logging]` section of `etc/config.ini` (creating the file
from the bundled sample when missing) with console and rotating-file output
enabled, and creates the log directory. Comments in the INI file are kept.

To also forward records to a Logstash server:

```bash
kardex log enable --logstash \
    --logstash-host logs.internal \
    --logstash-port 5044 \
    --logstash-level INFO
```

The Logstash handler requires `pip install navconfig[logstash]`.

Other options: `--loglevel`, `--logdir`, `--quiet` (no console output),
`--no-file` (no rotating file handler) and `--mailer` (email alerts on
CRITICAL records).

Apply the resulting configuration in your application:

```python
import logging
from logging.config import dictConfig
from navconfig.logging import logging_config

dictConfig(logging_config)

logger = logging.getLogger("MY_APP")
logger.info("Hello World")
```

Console output uses colored formatting by default:

```
[INFO] 2024-03-11 19:31:39,408 MY_APP: Hello World
```


## Accessing configuration

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
config.getboolean("DEBUG")              # bool
config.getlist("ALLOWED_HOSTS")         # list (comma-separated)
config.getdict("EXTRA")                 # dict
```

An optional `fallback` argument is returned when the key is not found:

```python
config.get("MISSING_KEY", "default_value")
```

### Initialization

NavConfig resolves the project layout and loads the environment the first
time one of its package-level names is accessed (`config`, `BASE_DIR`,
`DEBUG`, `ENV`, ...), not while the package is being imported. Call
`navconfig.bootstrap()` when you need the environment loaded into
`os.environ` as a side effect without touching any of those names:

```python
import navconfig

navconfig.bootstrap()
```


## Configuration directories

By default NavConfig looks for files relative to the project root:

| File type            | Default location               |
| -------------------- | ------------------------------ |
| `.env`               | `env/` (plus ENV subdirectory) |
| `.yml` / `.toml`     | `env/`                         |
| `pyproject.toml`     | project root                   |
| `.ini`               | `etc/`                         |

A typical project looks like this:

```text
myapp/
|-- __init__.py
|-- pyproject.toml
|-- env/
|   |-- .env          (shared base file)
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


## Custom settings module

You can create a Python package called `settings` in your project to define
additional configuration derived from NavConfig values.

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

Optional: `redis`, `python-logstash-async`, `uvloop`.


## Contribution guidelines

Please see the Contribution Guide for details on:

- Writing tests
- Code review process
- Other guidelines


## License

NavConfig is released under the MIT License.
