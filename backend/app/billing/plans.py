from __future__ import annotations

from fastapi import Depends, HTTPException, status

PLAN_ORDER = {"free": 0, "pro": 1, "premium": 2, "enterprise": 2}
PLAN_FEATURES = {
    "free": {"dashboard", "expenses_basic", "budget_basic"},
    "pro": {"dashboard", "expenses_basic", "budget_basic", "goals", "alerts", "diagnosis", "investments"},
    "premium": {"dashboard", "expenses_basic", "budget_basic", "goals", "alerts", "diagnosis", "investments", "automation", "api", "executive_reports"},
}


def has_plan(current_plan: str | None, required_plan: str) -> bool:
    return PLAN_ORDER.get((current_plan or "free").lower(), 0) >= PLAN_ORDER.get(required_plan.lower(), 0)


def has_feature(current_plan: str | None, feature: str) -> bool:
    plan = (current_plan or "free").lower()
    if feature in PLAN_FEATURES.get(plan, set()):
        return True
    return any(PLAN_ORDER.get(p, 0) <= PLAN_ORDER.get(plan, 0) and feature in feats for p, feats in PLAN_FEATURES.items())


def require_feature(feature: str):
    from backend.app.auth.dependencies import get_current_user

    def checker(user=Depends(get_current_user)):
        if not has_feature(user.get("plan"), feature):
            raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Recurso disponível em plano superior")
        return user

    return checker
