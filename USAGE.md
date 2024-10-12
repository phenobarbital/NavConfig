# Retrieving values

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

# Configuration directories

By default, `NavConfig` will look for configuration files the base path of project, based on the file type:

 * .env files will be searched on a `env/` directory.
 * .yml/.toml files will be searched on `env/` directory.
 * pyproject.toml file will be searched on root of project.
 * .ini files will be searched on `etc/` directory.
