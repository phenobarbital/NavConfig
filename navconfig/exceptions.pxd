# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
cdef class KardexError(Exception):
    """Base Exception for NavConfig, inherit by other exceptions"""

cdef class ReaderError(KardexError):
    """An error Triggered by Reader."""

cdef class LoaderError(KardexError):
    """A Feature is not supported"""

cdef class ConfigError(KardexError):
    """Runtime Error for bad configuration"""

cdef class ReaderNotSet(Exception):
    """Reader is Disabled."""
