from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any


class AdvisorPerformanceService:
    """Cache leve e compactação de contexto para manter o advisor rápido."""

    _context_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}

    @staticmethod
    def cache_key(organization_id: str, user_id: str, year: int | None = None, month: int | None = None) -> str:
        raw = f"{organization_id}:{user_id}:{year or 'current'}:{month or 'current'}"
        return sha256(raw.encode()).hexdigest()[:20]

    @classmethod
    def get_cached_context(cls, key: str) -> dict[str, Any] | None:
        row = cls._context_cache.get(key)
        if not row:
            return None
        expires, value = row
        if expires < datetime.now(timezone.utc):
            cls._context_cache.pop(key, None)
            return None
        return deepcopy(value)

    @classmethod
    def set_cached_context(cls, key: str, value: dict[str, Any], ttl_seconds: int = 120) -> None:
        cls._context_cache[key] = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds), deepcopy(value))
        if len(cls._context_cache) > 300:
            for old_key in list(cls._context_cache.keys())[:50]:
                cls._context_cache.pop(old_key, None)

    @staticmethod
    def compact_context(context: dict[str, Any], max_items: int = 8) -> dict[str, Any]:
        compact = deepcopy(context)
        for key in ["alerts", "next_steps", "goals"]:
            if isinstance(compact.get(key), list):
                compact[key] = compact[key][:max_items]
        if isinstance(compact.get("memory"), dict):
            compact["memory"] = {k: v for k, v in compact["memory"].items() if k in {"trend", "insights", "critical_categories", "patterns", "memory_strength"}}
        return compact
