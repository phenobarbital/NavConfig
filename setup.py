#!/usr/bin/env python
"""NavConfig.

    Configuration Service for Navigator and DataIntegrator.
See:
https://github.com/phenobarbital/NavConfig
"""
from os import path
from setuptools import setup, find_packages


def get_path(filename):
    return path.join(path.dirname(path.abspath(__file__)), filename)


with open(get_path('README.md')) as readme:
    README = readme.read()

with open(get_path('navconfig/version.py')) as meta:
    exec(meta.read())

setup(
    name=__title__,
    version=__version__,
    python_requires=">=3.8.0",
    url='https://github.com/phenobarbital/NavConfig',
    description='Configuration tool for Navigator Services',
    long_description=README,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3.8',
    ],
    author='Jesus Lara',
    author_email='jlara@trocglobal.com',
    packages=find_packages(),
    install_requires=[
        'wheel==0.37.0',
        'asyncio==3.4.3',
        'uvloop==0.16.0',
        'python-dotenv==0.15.0',
        'configparser==5.0.2',
        'PyYAML>=6.0',
        'PyDrive==1.3.1',
        'pylibmc==1.6.1',
        'objectpath==0.6.1',
        'iso8601==0.1.13',
        'pycparser==2.20',
        'redis==3.5.3',
        'python-rapidjson==1.5',
    ],
    project_urls={  # Optional
        'Source': 'https://github.com/phenobarbital/NavConfig',
        'Funding': 'https://paypal.me/phenobarbital',
        'Say Thanks!': 'https://saythanks.io/to/phenobarbital',
    },
)
