# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=False, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
"""
Parsing a YAML file.
"""
import yaml
import aiofiles

cdef class YAMLParser:
    async def parse(self, object filename):
        try:
            content = None
            async with aiofiles.open(filename) as f:
                content = await f.read()
            return yaml.load(content, Loader=yaml.SafeLoader)
        except Exception as err:
            raise RuntimeError(
                f'Error parsing Yaml content: {err!s}.'
            )
