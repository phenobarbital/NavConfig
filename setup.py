#!/usr/bin/env python
"""NavConfig.

    Configuration Service for Navigator and DataIntegrator.
See:
https://github.com/phenobarbital/NavConfig
"""

from setuptools import setup, find_packages

setup(
    name='navconfig',
    version=open("VERSION").read().strip(),
    python_requires=">=3.7.0",
    url='https://github.com/phenobarbital/NavConfig',
    description='Configuration tool for Navigator Services',
    long_description='Configuration tool for Navigator Services',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'Programming Language :: Python :: 3.7',
    ],
    author='Jesus Lara',
    author_email='jlara@trocglobal.com',
    packages=find_packages(),
    install_requires=[
        'asyncio==3.4.3',
        'python-dotenv==0.15.0',
        'configparser==5.0.1',
        'PyDrive==1.3.1',
        'pylibmc==1.6.1',
        'objectpath==0.6.1',
        'asyncdb'
    ],
    dependency_links=[
        'git+https://github.com/phenobarbital/asyncdb.git@master#egg=asyncdb'
    ],
    project_urls={  # Optional
        'Source': 'https://github.com/phenobarbital/NavConfig',
        'Funding': 'https://paypal.me/phenobarbital',
        'Say Thanks!': 'https://saythanks.io/to/phenobarbital',
    },
)
