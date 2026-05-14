from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PLAN_LIMITS: dict[str, dict[str, int | bool]] = {
    "free": {"users": 1, "expenses_per_month": 100, "accounts": 2, "cards": 1, "goals": 2, "active_alerts": 3, "backtests_per_month": 0, "jobs_per_month": 10, "exports": 1, "advanced_ai": False},
    "pro": {"users": 5, "expenses_per_month": 2_000, "accounts": 10, "cards": 5, "goals": 20, "active_alerts": 20, "backtests_per_month": 20, "jobs_per_month": 100, "exports": 20, "advanced_ai": True},
    "premium": {"users": 20, "expenses_per_month": 20_000, "accounts": 50, "cards": 20, "goals": 100, "active_alerts": 100, "backtests_per_month": 200, "jobs_per_month": 1_000, "exports": 200, "advanced_ai": True},
    "enterprise": {"users": 10_000, "expenses_per_month": 10_000_000, "accounts": 10_000, "cards": 10_000, "goals": 10_000, "active_alerts": 10_000, "backtests_per_month": 100_000, "jobs_per_month": 1_000_000, "exports": 100_000, "advanced_ai": True},
}

FEATURE_TABLES = {
    "users": ("organization_members", "organization_id", None),
    "accounts": ("erp_accounts", "organization_id", "deleted_at IS NULL"),
    "cards": ("erp_cards", "organization_id", "deleted_at IS NULL"),
    "goals": ("financial_goals", "organization_id", "deleted_at IS NULL"),
    "active_alerts": ("erp_alerts", "organization_id", "deleted_at IS NULL"),
    "jobs_per_month": ("enterprise_jobs", "organization_id", "created_at >= date_trunc('month', NOW())"),
    "backtests_per_month": ("enterprise_jobs", "organization_id", "job_type = 'backtest' AND created_at >= date_trunc('month', NOW())"),
    "expenses_per_month": ("erp_expenses", "organization_id", "deleted_at IS NULL AND created_at >= date_trunc('month', NOW())"),
}

class PlanLimitExceeded(Exception):
    pass

def get_plan_limits(plan: str | None) -> dict[str, int | bool]:
    return PLAN_LIMITS.get((plan or "free").lower(), PLAN_LIMITS["free"])

def plan_limit_payload(plan: str, feature: str, message: str) -> dict:
    return {"detail": "Plan limit reached", "limit": feature, "plan": plan, "upgrade_required": True, "message": message}

def ensure_feature_allowed(db: "Session", *, organization_id: str, plan: str, feature: str, increment: int = 1) -> None:
    limits = get_plan_limits(plan)
    limit = limits.get(feature)
    if limit is True or limit is None:
        return
    if limit is False or int(limit) <= 0:
        raise PlanLimitExceeded(f"Recurso indisponível no plano {plan}: {feature}")
    table_column = FEATURE_TABLES.get(feature)
    if not table_column:
        return
    table, column, extra = table_column
    try:
        try:
            from sqlalchemy import text
        except Exception:
            text = lambda x: x
        where = f"{column}=:organization_id"
        if extra:
            where += f" AND {extra}"
        current = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), {"organization_id": organization_id}).scalar() or 0
    except Exception:
        current = 0
    if int(current) + increment > int(limit):
        raise PlanLimitExceeded(f"Limite do plano excedido para {feature}: {current}/{limit}")
