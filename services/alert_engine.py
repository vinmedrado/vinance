
from __future__ import annotations

from typing import Any
from sqlalchemy import text

from db.database import SessionLocal


def evaluate_alerts(tenant_id: str) -> list[dict[str, Any]]:
    triggered: list[dict[str, Any]] = []
    try:
        from services.investor_service import get_opportunities
        opps = get_opportunities(tenant_id=tenant_id, limit=100)
        for _, row in opps.iterrows():
            if row.get("classificacao") == "Forte":
                triggered.append({
                    "tenant_id": tenant_id,
                    "ticker": row.get("ticker"),
                    "alert_type": "opportunity",
                    "message": f"{row.get('ticker')} virou oportunidade Forte.",
                    "score": row.get("score_final"),
                })
    except Exception as exc:
        triggered.append({"tenant_id": tenant_id, "alert_type": "health", "message": f"Erro ao avaliar alertas: {exc}"})

    try:
        with SessionLocal() as db:
            rows = db.execute(
                text("""
                    SELECT *
                    FROM user_alerts
                    WHERE tenant_id=:tenant_id AND is_active=true
                """),
                {"tenant_id": tenant_id},
            ).mappings().all()
            for alert in rows:
                # Motor mínimo: alertas persistidos são avaliados por tipo e podem ser expandidos depois.
                if alert["alert_type"] == "opportunity":
                    for item in triggered:
                        if not alert.get("ticker") or str(alert.get("ticker")) == str(item.get("ticker")):
                            item["user_id"] = alert.get("user_id")
    except Exception:
        pass
    return triggered


def send_alert_email(user_id: str, alert_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    # Integração SendGrid deve ser configurada em produção.
    return {"queued": True, "user_id": user_id, "alert_type": alert_type, "payload": payload}
