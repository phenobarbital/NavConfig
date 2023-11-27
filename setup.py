#!/usr/bin/env python
"""NavConfig.

    Configuration Service for Navigator and DataIntegrator.
See:
https://github.com/phenobarbital/NavConfig
"""
import ast
from os import path
from setuptools import find_packages, setup, Extension
from Cython.Build import cythonize


def get_path(filename):
    return path.join(path.dirname(path.abspath(__file__)), filename)


def readme():
    with open(get_path('README.md'), 'r', encoding='utf-8') as rd:
        return rd.read()


version = get_path('navconfig/version.py')
with open(version, 'r', encoding='utf-8') as meta:
    # exec(meta.read())
    t = compile(meta.read(), version, 'exec', ast.PyCF_ONLY_AST)
    for node in (n for n in t.body if isinstance(n, ast.Assign)):
        if len(node.targets) == 1:
            name = node.targets[0]
            if isinstance(name, ast.Name) and name.id in (
                '__version__',
                '__title__',
                '__description__',
                '__author__',
                '__license__',
                '__author_email__'
            ):
                v = node.value
                if name.id == '__version__':
                    __version__ = v.s
                if name.id == '__title__':
                    __title__ = v.s
                if name.id == '__description__':
                    __description__ = v.s
                if name.id == '__license__':
                    __license__ = v.s
                if name.id == '__author__':
                    __author__ = v.s
                if name.id == '__author_email__':
                    __author_email__ = v.s

COMPILE_ARGS = ["-O2"]

extensions = [
    Extension(
        name='navconfig.exceptions',
        sources=['navconfig/exceptions.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c"
    ),
    Extension(
        name='navconfig.utils.functions',
        sources=['navconfig/utils/functions.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    ),
    Extension(
        name='navconfig.utils.types',
        sources=['navconfig/utils/types.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    ),
    Extension(
        name='navconfig.loaders.parsers.toml',
        sources=['navconfig/loaders/parsers/toml.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    ),
    Extension(
        name='navconfig.loaders.parsers.yaml',
        sources=['navconfig/loaders/parsers/yaml.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    ),
    Extension(
        name='navconfig.logging.logger',
        sources=['navconfig/logging/logger.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    ),
    Extension(
        name='navconfig.utils.json',
        sources=['navconfig/utils/json.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c++"
    )
]

setup(
    name=__title__,
    version=__version__,
    python_requires=">=3.9.16",
    url='https://github.com/phenobarbital/NavConfig',
    description=__description__,
    long_description=readme(),
    long_description_content_type='text/markdown',
    license=__license__,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Framework :: AsyncIO'
    ],
    author='Jesus Lara',
    author_email='jesuslara@phenobarbital.info',
    packages=find_packages(exclude=["docs", "tests", "settings"]),
    setup_requires=[
        'wheel==0.42.0',
        'Cython==0.29.33'
    ],
    install_requires=[
        'asyncio==3.4.3',
        'uvloop==0.19.0',
        'python-dotenv==1.0.0',
        'configparser==5.3.0',
        'python-dateutil==2.8.2',
        'objectpath==0.6.1',
        'iso8601==1.1.0',
        'pycparser==2.21',
        "orjson==3.9.9",
        'pycryptodomex==3.17',
        "cryptography==37.0.4",
        'aiofiles==23.1.0',
        'aiofile==3.8.8',
    ],
    extras_require={
        "memcache": [
            "pylibmc==1.6.3",
            "aiomcache==0.8.1",
        ],
        "gdrive": [
            'PyDrive==1.3.1',
        ],
        "logstash": [
            'python-logstash-async==2.5.0',
            'aiologstash==2.0.0',
            'elasticsearch==8.10.1'
        ],
        "redis": [
            'redis==4.5.5',
            'aioredis==2.0.1',
        ],
        "toml": [
            'pytomlpp==1.0.11'
        ],
        "yaml": [
            'PyYAML>=6.0',
        ],
        "hvac": [
            "hvac==1.1.0"
        ],
        "default": [
            'pytomlpp==1.0.11',
            'redis==4.5.5',
            'aioredis==2.0.1',
            'python-logstash-async==2.5.0',
            'aiologstash==2.0.0',
            'PyYAML>=6.0',
            "hvac==1.1.0"
        ],
        "all": [
            'pytomlpp==1.0.11',
            'redis==4.5.5',
            'aioredis==2.0.1',
            'python-logstash-async==2.5.0',
            'aiologstash==2.0.0',
            'PyYAML>=6.0',
            "aiomcache==0.8.1",
            "hvac==1.1.0"
        ]
    },
    ext_modules=cythonize(extensions),
    project_urls={  # Optional
        'Source': 'https://github.com/phenobarbital/NavConfig',
        'Funding': 'https://paypal.me/phenobarbital',
        'Say Thanks!': 'https://saythanks.io/to/phenobarbital',
    },
)
