# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
cdef class KardexError(Exception):
    """Base Exception for Kardex, inherit by other exceptions"""

    code: int = 0

    def __init__(self, object message, int code = 0, **kwargs):
        super().__init__(message)
        if hasattr(message, 'message'):
            self.message = message.message
        else:
            self.message = str(message)
        self.stacktrace = None
        if 'stacktrace' in kwargs:
            self.stacktrace = kwargs['stacktrace']
        self.args = kwargs
        self.code = int(code)

    def __repr__(self):
        return f"{self.message}"

    def __str__(self):
        return f"{self.message}"

cdef class ReaderError(KardexError):
    """An error Triggered by Reader."""

cdef class LoaderError(KardexError):
    """A Feature is not supported"""

cdef class ConfigError(KardexError):
    """Runtime Error for bad configuration"""

cdef class ReaderNotSet(Exception):
    """Reader is Disabled."""
