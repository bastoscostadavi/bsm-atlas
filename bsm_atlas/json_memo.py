"""Bounded process-local memoization of pure specification calculations.

Only exact built-in JSON values enter the cache. Other Python inputs still go
through the original validator, without JSON coercions hiding invalid types.
No cache is persisted, exceptions are never cached, and callers own their copy.
"""
from copy import deepcopy
from functools import lru_cache, wraps
import json
from math import isfinite


def _plain_json(value):
    kind = type(value)
    if kind in (str, int, bool, type(None)):
        return True
    if kind is float:
        return isfinite(value)
    if kind is list:
        return all(_plain_json(item) for item in value)
    if kind is dict:
        return all(type(key) is str and _plain_json(item) for key, item in value.items())
    return False


def memoized_specification(maxsize=1024):
    """Reuse an exact calculation, not a previous decision about a model name."""
    def decorate(function):
        @lru_cache(maxsize=maxsize)
        def cached(encoded):
            return function(json.loads(encoded))

        @wraps(function)
        def wrapped(specification):
            try:
                cacheable = _plain_json(specification)
            except RecursionError:
                cacheable = False
            if not cacheable:
                return function(specification)
            encoded = json.dumps(specification, sort_keys=True, separators=(',', ':'),
                                 ensure_ascii=True, allow_nan=False)
            return deepcopy(cached(encoded))

        wrapped.cache_info = cached.cache_info
        wrapped.cache_clear = cached.cache_clear
        return wrapped
    return decorate
