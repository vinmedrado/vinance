from __future__ import annotations

import asyncio
from functools import lru_cache

from redis.asyncio import Redis

from backend.app.core.config import settings


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def validate_redis_connection() -> bool:
    client = get_redis_client()
    for attempt in range(settings.redis_health_retries):
        try:
            return bool(await client.ping())
        except Exception:
            if attempt + 1 >= settings.redis_health_retries:
                return False
            await asyncio.sleep(0.2 * (attempt + 1))
    return False


async def close_redis() -> None:
    await get_redis_client().aclose()
