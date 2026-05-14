from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from backend.app.core.settings import get_settings

router = APIRouter(prefix="/analytics", tags=["analytics"])
logger = logging.getLogger("financeos.analytics")


class AnalyticsEvent(BaseModel):
    event: str = Field(min_length=2, max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None


@router.post("/track")
async def track_event(payload: AnalyticsEvent, request: Request):
    settings = get_settings()
    record = {
        "event": payload.event,
        "properties": payload.properties,
        "user_id": payload.user_id,
        "ip": request.client.host if request.client else None,
        "ts": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
    }
    logger.info("analytics_event", extra=record)
    return {"accepted": True, "enabled": settings.analytics_enabled}
