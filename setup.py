#!/usr/bin/env python
"""NavConfig setup.py - Cython extensions only.

All package metadata lives in ``pyproject.toml``; this file only declares and
compiles the Cython extension modules.
"""
from Cython.Build import cythonize
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext

# Optimization flag per compiler family. MSVC happens to accept ``-O2`` as an
# alias for ``/O2``, but that is an undocumented convenience of the ``-``/``/``
# option prefixes, not a contract -- so the flag is selected explicitly for the
# toolchain actually in use (gcc on manylinux, clang on macOS, cl.exe on
# Windows). Nothing here is architecture-specific: the Apple Silicon wheels
# need no extra flags because the extensions link nothing outside libSystem.
OPTIMIZATION_FLAGS = {
    "msvc": ["/O2"],
    "unix": ["-O2"],
}


class build_ext(_build_ext):
    """``build_ext`` that injects the optimization flag for the real compiler.

    The extensions below intentionally declare no ``extra_compile_args``: the
    concrete compiler is only known once ``setuptools`` has probed the host, so
    the flag is appended here instead of being hardcoded to a GCC spelling.
    """

    def build_extensions(self) -> None:
        """Append the compiler-appropriate optimization flag, then build.

        Returns:
            None.
        """
        flags: list[str] = OPTIMIZATION_FLAGS.get(
            self.compiler.compiler_type, OPTIMIZATION_FLAGS["unix"]
        )
        for extension in self.extensions:
            extension.extra_compile_args = list(extension.extra_compile_args or [])
            extension.extra_compile_args.extend(
                flag for flag in flags if flag not in extension.extra_compile_args
            )
        super().build_extensions()


# Define Cython extensions
extensions = [
    Extension(
        name='navconfig.exceptions',
        sources=['navconfig/exceptions.pyx'],
        language="c"
    ),
    Extension(
        name='navconfig.utils.functions',
        sources=['navconfig/utils/functions.pyx'],
        language="c++"
    ),
    Extension(
        name='navconfig.utils.types',
        sources=['navconfig/utils/types.pyx'],
        language="c++"
    ),
    Extension(
        name='navconfig.loaders.parsers.toml',
        sources=['navconfig/loaders/parsers/toml.pyx'],
        language="c++"
    ),
    Extension(
        name='navconfig.loaders.parsers.yaml',
        sources=['navconfig/loaders/parsers/yaml.pyx'],
        language="c++"
    ),
    Extension(
        name='navconfig.logging.logger',
        sources=['navconfig/logging/logger.pyx'],
        language="c++"
    ),
    Extension(
        name='navconfig.utils.json',
        sources=['navconfig/utils/json.pyx'],
        language="c++"
    )
]

# Setup only handles Cython extensions
# All other configuration is in pyproject.toml
setup(
    cmdclass={"build_ext": build_ext},
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
