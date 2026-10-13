from __future__ import annotations

import hashlib

from fastapi import HTTPException, status

from backend.app.core.config import settings
from backend.app.core.redis import get_redis_client


async def enforce_auth_rate_limit(scope: str, identifier: str, limit: int) -> None:
    if not settings.effective_rate_limiting_enabled:
        return
    digest = hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()
    key = f"rate-limit:auth:{scope}:{digest}"
    try:
        client = get_redis_client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, settings.auth_rate_limit_window_seconds)
    except Exception as exc:
        if settings.is_production:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication temporarily unavailable") from exc
        return
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts",
            headers={"Retry-After": str(settings.auth_rate_limit_window_seconds)},
        )
