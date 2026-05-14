from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from backend.app.intelligence.models import UserLearningProfile


class UserLearningProfileService:
    """Aprendizado progressivo por organização/usuário, sem expor dados entre tenants."""

    @staticmethod
    def _decode(text: str | None) -> list[str]:
        try:
            value = json.loads(text or "[]")
            return value if isinstance(value, list) else []
        except Exception:
            return []

    @classmethod
    def get_or_create(cls, db: Session, *, organization_id: str, user_id: str) -> UserLearningProfile:
        row = db.query(UserLearningProfile).filter(
            UserLearningProfile.organization_id == organization_id,
            UserLearningProfile.user_id == user_id,
        ).first()
        if not row:
            row = UserLearningProfile(organization_id=organization_id, user_id=user_id)
            db.add(row)
            db.flush()
        return row

    @classmethod
    def to_dict(cls, row: UserLearningProfile) -> dict[str, Any]:
        return {
            "organization_id": row.organization_id,
            "user_id": row.user_id,
            "financial_literacy_level": row.financial_literacy_level,
            "preferred_tone": row.preferred_tone,
            "preferred_detail_level": row.preferred_detail_level,
            "observed_risk_behavior": row.observed_risk_behavior,
            "recurring_challenges": cls._decode(row.recurring_challenges),
            "engagement_score": row.engagement_score,
            "last_updated_at": row.last_updated_at,
        }

    @classmethod
    def update_from_interaction(cls, db: Session, *, organization_id: str, user_id: str, question: str = "", context: dict[str, Any] | None = None) -> dict[str, Any]:
        row = cls.get_or_create(db, organization_id=organization_id, user_id=user_id)
        q = (question or "").lower()
        challenges = set(cls._decode(row.recurring_challenges))
        if any(w in q for w in ("dívida", "divida", "quitar", "atrasada")):
            challenges.add("dívidas/contas")
        if any(w in q for w in ("investir", "aporte", "carteira")):
            challenges.add("investimentos")
        if any(w in q for w in ("gasto", "despesa", "categoria")):
            challenges.add("controle de gastos")
        if any(w in q for w in ("por que", "explica", "entender")):
            row.preferred_detail_level = "medium"
        if context:
            health = context.get("health", {})
            score = int(health.get("health_score", 50) or 50)
            if score < 45:
                row.observed_risk_behavior = "defensive"
            elif score > 75:
                row.observed_risk_behavior = "confident"
            row.engagement_score = min(100, max(0, int(row.engagement_score or 50) + 2))
        row.recurring_challenges = json.dumps(sorted(challenges), ensure_ascii=False)
        db.flush()
        return cls.to_dict(row)
