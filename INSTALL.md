 # Installation instructions on Linux

for Debian-based systems, project requires wheel and cython for installation.

```
apt install build-essential gcc python3.11-dev python3.11-venv
```

## First Steps.

Navconfig is a configuration tool, is a combination of Dotenv (for managing .env files), hashicorp vault (optional), ini files and python-style settings (a settings.py file like Django).

Main requirement is a .env file, that file can be empty.

```
mkdir env
touch env/.env
```

optionally, you can create a empty ini file (for saving configurations) and add a reference for that file in .env file.

```
mkdir etc
touch etc/config.ini

echo "CONFIG_FILE=etc/config.ini" > env/.env
```

and that's it.
Navconfig is ready to use.
