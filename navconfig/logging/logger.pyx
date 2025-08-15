# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
import sys
import asyncio
from typing import Optional, Union
from logging.config import dictConfig
from libcpp cimport bool as bool_t
import traceback
from logging import setLoggerClass
from navconfig import config, DEBUG
from navconfig.utils.json import json_decoder, json_encoder
from navconfig.logging.formatter import logging, VerboseLogger, ColoredFormatter


### Logging
if DEBUG is True:
    LOGLEVEL = logging.DEBUG
else:
    LOGLEVEL = logging.INFO


cdef class Logger:
    __slots__ = ['name', '_debug', '_logger', 'logger', '_console_added']
    cdef bool_t _debug
    cdef str name
    cdef object _logger
    cdef bool_t _console_added

    def __init__(self, name: str = '', config: dict = None, **kwargs) -> None:
        ### Logging handler:
        self.name = ''
        if not name:
            self.name = __name__
        else:
            self.name = name
        self._debug = kwargs.get('debug', DEBUG)
        self._console_added = False

        if config:
            dictConfig(config)
        setLoggerClass(VerboseLogger)
        self._logger = logging.getLogger(self.name)
        self._logger.setLevel(LOGLEVEL)

    def addConsole(self) -> None:
        """Add console handler with colors if not already added."""
        if self._console_added:
            return

        # Check if console handler already exists
        for handler in self._logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                # Console handler already exists, just update formatter if needed
                if not isinstance(handler.formatter, ColoredFormatter):
                    handler.setFormatter(ColoredFormatter())
                self._console_added = True
                return

        # No console handler found, add one
        ch = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(ColoredFormatter())
        self._logger.addHandler(ch)

        # Prevent propagation to avoid duplicates
        self._logger.propagate = False

        ## also, changing the logLevel of root logger
        self._logger.setLevel(logging.DEBUG)
        self._console_added = True

    def removeConsole(self) -> None:
        """Remove console handlers."""
        handlers_to_remove = []
        for handler in self._logger.handlers:
            if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
                handlers_to_remove.append(handler)

        for handler in handlers_to_remove:
            self._logger.removeHandler(handler)

        self._console_added = False

    @property
    def logger(self):
        return self._logger

    def disable(self, name: str, loglevel = logging.CRITICAL):
        ## disable logger
        aio = logging.getLogger(name)
        aio.setLevel(loglevel)

    def setLevel(self, level) -> None:
        self._logger.setLevel(level)

    def addHandler(self, handler) -> None:
        self._logger.addHandler(handler)

    def setName(self, name: str):
        ## change the logger:
        logging.Logger.manager.loggerDict[self.name].name = name
        self.name = name

    def info(self, message, *args, serialize = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        self._logger.info(msg, *args, **kwargs)

    def notice(self, message, *args, serialize = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        self._logger.notice(msg, *args, **kwargs)

    def debug(self, message, *args, serialize = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        self._logger.debug(msg, *args, **kwargs)

    def verbose(self, message, *args, serialize = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        self._logger.verbose(msg, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._logger.warning(message, *args, **kwargs)

    def error(self, message, *args, serialize = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        self._logger.error(msg, *args, **kwargs)

    def critical(self, message, *args, serialize = False, stacktrace = False, **kwargs):
        if callable(message):
            msg = message(*args, **kwargs)
        else:
            msg = message
        if serialize is True:
            msg = json_encoder(msg)
        if stacktrace is True:
            stack = ColoredFormatter.darkgrey + traceback.format_exc() + ColoredFormatter.reset
            error = ColoredFormatter.bold_red + msg + ColoredFormatter.reset
            msg = f"-\r\n{stack}\r\n{error}"
        self._logger.critical(msg, *args, **kwargs)
