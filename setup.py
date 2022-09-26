#!/usr/bin/env python
"""NavConfig.

    Configuration Service for Navigator and DataIntegrator.
See:
https://github.com/phenobarbital/NavConfig
"""
from os import path
from setuptools import find_packages, setup, Extension
from Cython.Build import cythonize


def get_path(filename):
    return path.join(path.dirname(path.abspath(__file__)), filename)


def readme():
    with open(get_path('README.md')) as readme:
        return readme.read()


with open(get_path('navconfig/version.py')) as meta:
    exec(meta.read())

COMPILE_ARGS = ["-O2"]

extensions = [
    Extension(
        name='navconfig.utils.functions',
        sources=['navconfig/utils/functions.pyx'],
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
    )
]

setup(
    name=__title__,
    version=__version__,
    python_requires=">=3.8.0",
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
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Framework :: AsyncIO'
    ],
    author='Jesus Lara',
    author_email='jesuslara@phenobarbital.info',
    packages=find_packages(),
    setup_requires=[
        'wheel==0.37.1',
        'cython==0.29.32'
    ],
    install_requires=[
        'wheel==0.37.1',
        'asyncio==3.4.3',
        'uvloop==0.17.0',
        'python-dotenv==0.20.0',
        'configparser==5.2.0',
        'python-dateutil==2.8.2',
        'objectpath==0.6.1',
        'iso8601==1.0.2',
        'pycparser==2.21',
        'orjson==3.8.0',
        'pycryptodomex==3.15.0',
        "cryptography==37.0.4",
        'aiofiles==0.8.0'
    ],
    extras_require = {
        "memcache": [
            "pylibmc==1.6.1",
            "aiomcache==0.7.0",
        ],
        "gdrive": [
            'PyDrive==1.3.1',
        ],
        "logstash": [
            'python-logstash-async==2.5.0',
            'aiologstash==2.0.0',
        ],
        "redis": [
            'redis==4.3.4',
            'aioredis==2.0.1',
        ],
        "toml": [
            'pytomlpp==1.0.11'
        ],
        "yaml": [
          'PyYAML>=6.0',
        ],
        "default": [
            'pytomlpp==1.0.11',
            'redis==4.3.4',
            'aioredis==2.0.1',
            'python-logstash-async==2.5.0',
            'aiologstash==2.0.0',
            'PyYAML>=6.0',
        ]
    },
    ext_modules=cythonize(extensions),
    project_urls={  # Optional
        'Source': 'https://github.com/phenobarbital/NavConfig',
        'Funding': 'https://paypal.me/phenobarbital',
        'Say Thanks!': 'https://saythanks.io/to/phenobarbital',
    },
)
