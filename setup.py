#!/usr/bin/env python
"""
NavConfig setup.py - Cython extensions only.

All package metadata is now in pyproject.toml.
This file only handles Cython compilation.
"""
from setuptools import setup, Extension
from Cython.Build import cythonize

COMPILE_ARGS = ["-O2"]

# Define Cython extensions
extensions = [
    Extension(
        name='navconfig.exceptions',
        sources=['navconfig/exceptions.pyx'],
        extra_compile_args=COMPILE_ARGS,
        language="c",
        define_macros=[('CYTHON_COMPILING_IN_PYPY', '1')]
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

# Setup only handles Cython extensions
# All other configuration is in pyproject.toml
setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            'language_level': 3,
            'embedsignature': True,
            'boundscheck': False,
            'wraparound': False,
            'initializedcheck': False,
        }
    ),
)
