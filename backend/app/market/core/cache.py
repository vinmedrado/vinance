from __future__ import annotations

import json
import os
import time
from typing import Any

try:  # Redis é opcional; em produção defina REDIS_URL.
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class CacheBackend:
    def get(self, key: str) -> Any: raise NotImplementedError
    def set(self, key: str, value: Any, ttl: int | None = None) -> None: raise NotImplementedError


class TTLCache(CacheBackend):
    def __init__(self, default_ttl: int = 900):
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any:
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if expires_at < time.time():
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._store[key] = (time.time() + (ttl or self.default_ttl), value)


class RedisCache(CacheBackend):
    def __init__(self, url: str, default_ttl: int = 900):
        if redis is None:
            raise RuntimeError("Pacote redis não instalado")
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.client.setex(key, ttl or self.default_ttl, json.dumps(value, default=str))


def build_cache() -> CacheBackend:
    redis_url = os.getenv("REDIS_URL")
    default_ttl = int(os.getenv("MARKET_CACHE_TTL_SECONDS", "900"))
    if redis_url:
        try:
            return RedisCache(redis_url, default_ttl=default_ttl)
        except Exception:
            # Falha segura para desenvolvimento local.
            return TTLCache(default_ttl=default_ttl)
    return TTLCache(default_ttl=default_ttl)


cache = build_cache()
