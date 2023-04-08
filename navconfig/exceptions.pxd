# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
cdef class NavConfigError(Exception):
    """Base Exception for NavConfig, inherit by other exceptions"""

cdef class ReaderError(NavConfigError):
    """An error Triggered by Reader."""

cdef class LoaderError(NavConfigError):
    """A Feature is not supported"""

cdef class ConfigError(NavConfigError):
    """Runtime Error for bad configuration"""
