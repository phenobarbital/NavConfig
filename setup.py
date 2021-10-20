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
    python_requires=">=3.8.0",
    url='https://github.com/phenobarbital/NavConfig',
    description='Configuration tool for Navigator Services',
    long_description='Configuration tool for Navigator Services',
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
        "wheel==0.37.0",
        'asyncio==3.4.3',
        'python-dotenv==0.15.0',
        'configparser==5.0.2',
        'PyDrive==1.3.1',
        'pylibmc==1.6.1',
        'objectpath==0.6.1',
        'python-logstash-async==2.2.0',
        'asyncdb>1.7.18'
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
