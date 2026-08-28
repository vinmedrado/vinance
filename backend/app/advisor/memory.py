from __future__ import annotations

import json
from typing import Protocol

from backend.app.core.redis import get_redis_client
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

MEMORY_TTL_SECONDS = 60 * 60 * 24
MAX_MEMORY_MESSAGES = 10


class RedisLike(Protocol):
    async def lrange(self, name: str, start: int, end: int): ...
    async def rpush(self, name: str, value: str): ...
    async def ltrim(self, name: str, start: int, end: int): ...
    async def expire(self, name: str, time: int): ...


def _memory_key(user_id: int) -> str:
    return f"vinance:advisor:memory:{user_id}"


async def get_memory(user_id: int, *, redis_client: RedisLike | None = None) -> list[dict[str, str]]:
    client = redis_client or get_redis_client()
    key = _memory_key(user_id)
    try:
        raw_items = await client.lrange(key, -MAX_MEMORY_MESSAGES, -1)
    except Exception as exc:
        logger.warning("advisor_memory_read_failed", extra={"user_id": user_id, "error": str(exc)})
        return []

    messages: list[dict[str, str]] = []
    for raw in raw_items or []:
        try:
            item = json.loads(raw)
            if item.get("role") in {"user", "assistant"} and item.get("content"):
                messages.append({"role": item["role"], "content": str(item["content"])[:1200]})
        except Exception:
            continue
    return messages[-MAX_MEMORY_MESSAGES:]


async def save_message(user_id: int, *, role: str, content: str, redis_client: RedisLike | None = None) -> None:
    if role not in {"user", "assistant"} or not content:
        return
    client = redis_client or get_redis_client()
    key = _memory_key(user_id)
    payload = json.dumps({"role": role, "content": content[:1200]}, ensure_ascii=False)
    try:
        await client.rpush(key, payload)
        await client.ltrim(key, -MAX_MEMORY_MESSAGES, -1)
        await client.expire(key, MEMORY_TTL_SECONDS)
    except Exception as exc:
        logger.warning("advisor_memory_write_failed", extra={"user_id": user_id, "error": str(exc)})


async def save_exchange(user_id: int, *, user_message: str, assistant_message: str, redis_client: RedisLike | None = None) -> None:
    await save_message(user_id, role="user", content=user_message, redis_client=redis_client)
    await save_message(user_id, role="assistant", content=assistant_message, redis_client=redis_client)
