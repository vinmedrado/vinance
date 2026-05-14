from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass
class AdvisorMessage:
    role: str
    content: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    intent: str | None = None


class ConversationalMemoryService:
    """Memória conversacional longa, isolada por organização/usuário.

    A implementação foi desenhada para funcionar sem dependência externa. Em produção,
    os dicionários podem ser substituídos pelas tabelas advisor_conversations,
    advisor_messages e advisor_memory_summaries mantendo a mesma interface.
    """

    _store: dict[str, list[AdvisorMessage]] = {}
    _summaries: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(organization_id: str, user_id: str, conversation_id: str | None = None) -> str:
        conv = conversation_id or "default"
        return f"{organization_id}:{user_id}:{conv}"

    @classmethod
    def add_turn(
        cls,
        *,
        organization_id: str,
        user_id: str,
        question: str,
        answer: str,
        intent: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        key = cls._key(organization_id, user_id, conversation_id)
        cls._store.setdefault(key, [])
        cls._store[key].append(AdvisorMessage(role="user", content=question, intent=intent))
        cls._store[key].append(AdvisorMessage(role="advisor", content=answer, intent=intent))
        cls._store[key] = cls._store[key][-40:]
        summary = cls.summarize(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
        cls._summaries[key] = summary
        return summary

    @classmethod
    def recent_context(cls, *, organization_id: str, user_id: str, conversation_id: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        key = cls._key(organization_id, user_id, conversation_id)
        return [m.__dict__ for m in cls._store.get(key, [])[-limit:]]

    @classmethod
    def summarize(cls, *, organization_id: str, user_id: str, conversation_id: str | None = None) -> dict[str, Any]:
        key = cls._key(organization_id, user_id, conversation_id)
        messages = cls._store.get(key, [])
        text = " ".join(m.content.lower() for m in messages[-24:])
        themes = []
        mapping = {
            "dívida": ["dívida", "divida", "quitar", "atrasada"],
            "investimentos": ["invest", "aporte", "carteira", "cripto", "etf", "fii"],
            "metas": ["meta", "viagem", "carro", "imóvel", "aposentadoria"],
            "orçamento": ["gasto", "despesa", "orçamento", "categoria", "lazer"],
            "reserva": ["reserva", "emergência", "caixa"],
        }
        for theme, words in mapping.items():
            if any(w in text for w in words):
                themes.append(theme)
        decisions = [m.content for m in messages if m.role == "advisor" and any(w in m.content.lower() for w in ["prior", "recom", "próximo", "foco"])]
        return {
            "conversation_id": conversation_id or "default",
            "memory_hash": sha256(key.encode()).hexdigest()[:12],
            "turns": len(messages) // 2,
            "recurring_themes": themes[:6],
            "recent_decisions": decisions[-5:],
            "recent_context": cls.recent_context(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id, limit=6),
            "summary": cls._human_summary(themes, decisions),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _human_summary(themes: list[str], decisions: list[str]) -> str:
        if not themes and not decisions:
            return "Ainda há pouca conversa acumulada. O advisor deve usar principalmente os dados atuais do ERP."
        theme_text = ", ".join(themes) if themes else "situação financeira geral"
        return f"Conversas recentes indicam foco em {theme_text}. Use esse histórico para manter continuidade e evitar respostas repetitivas."

    @classmethod
    def get_summary(cls, *, organization_id: str, user_id: str, conversation_id: str | None = None) -> dict[str, Any]:
        key = cls._key(organization_id, user_id, conversation_id)
        return cls._summaries.get(key) or cls.summarize(organization_id=organization_id, user_id=user_id, conversation_id=conversation_id)
