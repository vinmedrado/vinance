from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from time import perf_counter
from typing import Any


@dataclass
class AIUsageEvent:
    organization_id: str
    user_id: str
    question_hash: str
    topic: str
    intent: str
    provider: str
    success: bool
    latency_ms: int
    feedback: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AIAnalyticsService:
    """Analytics de IA sem armazenar prompt completo sensível."""

    _events: list[AIUsageEvent] = []

    @staticmethod
    def detect_topic(question: str, intent: str | None = None) -> str:
        q = (question or "").lower()
        if any(w in q for w in ["dívida", "divida", "quitar"]):
            return "debt"
        if any(w in q for w in ["invest", "aporte", "carteira"]):
            return "investment"
        if any(w in q for w in ["meta", "viagem", "carro", "aposentadoria"]):
            return "goals"
        if any(w in q for w in ["gasto", "despesa", "orçamento", "categoria"]):
            return "budget"
        return intent or "general"

    @staticmethod
    def start_timer() -> float:
        return perf_counter()

    @classmethod
    def record_usage(cls, *, organization_id: str, user_id: str, question: str, intent: str, provider: str, success: bool, started_at: float, feedback: str | None = None) -> dict[str, Any]:
        event = AIUsageEvent(
            organization_id=organization_id,
            user_id=user_id,
            question_hash=sha256((question or "").encode()).hexdigest()[:16],
            topic=cls.detect_topic(question, intent),
            intent=intent,
            provider=provider,
            success=success,
            latency_ms=int((perf_counter() - started_at) * 1000),
            feedback=feedback,
        )
        cls._events.append(event)
        cls._events = cls._events[-1000:]
        return event.__dict__

    @classmethod
    def report(cls, *, organization_id: str, user_id: str | None = None) -> dict[str, Any]:
        events = [e for e in cls._events if e.organization_id == organization_id and (user_id is None or e.user_id == user_id)]
        topics: dict[str, int] = {}
        for e in events:
            topics[e.topic] = topics.get(e.topic, 0) + 1
        return {
            "total_interactions": len(events),
            "success_rate": round(sum(1 for e in events if e.success) / max(len(events), 1), 3),
            "avg_latency_ms": int(sum(e.latency_ms for e in events) / max(len(events), 1)) if events else 0,
            "recurring_topics": sorted(topics.items(), key=lambda x: x[1], reverse=True)[:8],
        }
