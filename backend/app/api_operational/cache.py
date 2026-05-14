
from __future__ import annotations

import functools
import time
from threading import RLock
from typing import Any, Callable, Hashable

_CACHE: dict[Hashable, tuple[float, Any]] = {}
_LOCK = RLock()

def _make_key(func_name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Hashable:
    safe_args = tuple(repr(a) for a in args)
    safe_kwargs = tuple(sorted((k, repr(v)) for k, v in kwargs.items()))
    return (func_name, safe_args, safe_kwargs)

def ttl_cache(ttl_seconds: int = 60) -> Callable:
    """Small in-memory TTL cache for read-only API endpoints.

    The cache is intentionally process-local and lightweight. It is used only for
    GET/read endpoints and never for write operations or pipeline execution.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            now = time.time()
            key = _make_key(func.__name__, args, kwargs)
            with _LOCK:
                cached = _CACHE.get(key)
                if cached and cached[0] > now:
                    return cached[1]
            value = func(*args, **kwargs)
            with _LOCK:
                _CACHE[key] = (now + ttl_seconds, value)
            return value
        return wrapper
    return decorator

def clear_cache() -> None:
    with _LOCK:
        _CACHE.clear()

def cache_stats() -> dict[str, int]:
    with _LOCK:
        return {"entries": len(_CACHE)}
