
from __future__ import annotations

PLAN_LIMITS = {
    "free": {"assets": 50, "backtests": 5, "ml_models": 3, "alerts": 0, "api_access": False},
    "pro": {"assets": 500, "backtests": 50, "ml_models": 20, "alerts": 999, "api_access": True},
    "enterprise": {"assets": 999999, "backtests": 999999, "ml_models": 999999, "alerts": 999999, "api_access": True},
}


class PlanLimitExceeded(Exception):
    pass


def get_tenant_plan(tenant_id: str | None = None) -> str:
    if not tenant_id:
        return "free"

    # SQLite legado
    try:
        from db.database import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT plan FROM tenants WHERE id=? AND (is_active=1 OR is_active=true)",
            (str(tenant_id),),
        ).fetchone()
        conn.close()
        if row:
            return str(row[0] if isinstance(row, tuple) else row["plan"])
    except Exception:
        pass

    # PostgreSQL/SQLAlchemy
    try:
        from db.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        row = db.execute(
            text("SELECT plan FROM tenants WHERE id=:id AND is_active=true"),
            {"id": str(tenant_id)},
        ).mappings().first()
        db.close()
        if row:
            return str(row["plan"])
    except Exception:
        pass

    return "free"


def check_limit(tenant_id: str | None, resource: str, current_count: int):
    plan = get_tenant_plan(tenant_id)
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).get(resource)
    if limit is not None and current_count >= int(limit):
        raise PlanLimitExceeded(f"Limite atingido para {resource}: {limit} no plano {plan}")
    return True
