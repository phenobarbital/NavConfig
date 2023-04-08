# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
cdef class NavConfigError(Exception):
    """Base Exception for NavConfig, inherit by other exceptions"""

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
        return f"{self.message}, code: {self.code}"

    def __str__(self):
        return f"{self.message}, code: {self.code}"

cdef class ReaderError(NavConfigError):
    """An error Triggered by Reader."""

cdef class LoaderError(NavConfigError):
    """A Feature is not supported"""

cdef class ConfigError(NavConfigError):
    """Runtime Error for bad configuration"""
