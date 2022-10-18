# cython: language_level=3, embedsignature=True, boundscheck=False, wraparound=True, initializedcheck=False
# Copyright (C) 2018-present Jesus Lara
#
import time
import orjson
from collections.abc import Sequence
from decimal import Decimal
from datetime import timezone
from cpython cimport datetime
from zoneinfo import ZoneInfo
from dateutil.parser import parse, ParserError


cpdef object strtobool(object val):
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    if isinstance(val, bool):
        return val
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return True
    elif val in ('n', 'no', 'f', 'false', 'off', '0', 'null'):
        return False
    else:
        raise ValueError(
            f"invalid truth value for {val}"
        )


cpdef datetime.date to_date(object value, str mask = "%Y-%m-%d %H:%M:%S", str tz = None):
    if isinstance(value, datetime.datetime):
        return value
    else:
        try:
            result = datetime.datetime.strptime(str(value), mask)
            if tz is not None:
                zone = ZoneInfo(key=tz)
                result = result.replace(tzinfo=zone)
            return result
        except (TypeError, ValueError, AttributeError):
            return parse(str(value))


cpdef datetime.time to_time(object value, str mask = "%H:%M:%S"):
    if value == 0:
        return datetime.datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    if isinstance(value, datetime.time):
        return value
    elif isinstance(value, datetime.datetime):
        return value.time()
    else:
        if len(str(value)) < 6:
            value = str(value).zfill(6)
        try:
            return datetime.datetime.strptime(str(value), mask)
        except ValueError:
            return datetime.datetime.strptime(str(value), "%H:%M:%S")


cpdef datetime.datetime to_datetime(object value, str mask = "%Y-%m-%d %H:%M:%S"):
    if isinstance(value, datetime.datetime):
        return value
    elif isinstance(value, list):
        dt = to_date(value[0], mask=mask[0])
        mt = to_time(value[1], mask=mask[1]).time()
        return datetime.datetime.combine(dt, mt)
    else:
        if value is None:
            return datetime.datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            return datetime.datetime.strptime(str(value), mask)


cpdef datetime.datetime epoch_to_date(object value, str tz = None):
    if value is None:
        return None
    if len(str(value)) == 10:
        s = value
    elif len(str(value)) == 19:
        s = value / 1e9
    else:
        s, _ = divmod(value, 1000.0)
    if tz is not None:
        zone = ZoneInfo(key=tz)
    else:
        zone = timezone.utc
    return datetime.datetime.fromtimestamp(s, zone)


cpdef object to_boolean(object value):
    if isinstance(value, bool):
        return value
    elif value is None:
        return False
    else:
        try:
            return strtobool(value)
        except ValueError:
            return False


cpdef object is_date(object value):
        if isinstance(value, (datetime.datetime, time, datetime.time, datetime.timedelta)):
            return True
        else:
            try:
                val = parse(value)
                if val:
                    return True
                return False
            except (ParserError, ValueError):
                return False


cpdef object is_boolean(object value):
    return isinstance(value, bool)


class SafeDict(dict):
    """
    SafeDict.

    Allow to using partial format strings

    """

    def __missing__(self, str key):
        """Missing method for SafeDict."""
        return "{" + key + "}"
