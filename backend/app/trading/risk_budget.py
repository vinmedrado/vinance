from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.action_plan import service as action_plan_service
from backend.app.continuous_autopilot import service as continuous_service
from backend.trading.paper_trading_v2.config import DEFAULT_CONFIG

from .schemas import TradingRiskBudgetRead


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fingerprints(
    plan: Mapping[str, Any], context: Mapping[str, Any], continuous: Mapping[str, Any]
) -> dict[str, str]:
    values = {
        "state": context.get("state", {}).get("decision_fingerprint")
        or plan.get("state_fingerprint"),
        "policy": context.get("policy", {}).get("decision_fingerprint")
        or plan.get("policy_fingerprint"),
        "allocation": context.get("allocation", {}).get("decision_fingerprint")
        or plan.get("allocation_fingerprint"),
        "orchestration": context.get("orchestration", {}).get("decision_fingerprint")
        or plan.get("orchestration_fingerprint"),
        "action_plan": plan.get("decision_fingerprint"),
        "continuous": continuous.get("decision_fingerprint"),
    }
    return {key: str(value) for key, value in values.items() if value}


def build_risk_budget(
    *,
    household_id: int,
    plan: Mapping[str, Any],
    context: Mapping[str, Any],
    continuous: Mapping[str, Any],
) -> TradingRiskBudgetRead:
    state = dict(context.get("state") or {})
    policy = dict(context.get("policy") or {})
    allocation = dict(context.get("allocation") or {})
    readiness = str(policy.get("investment_readiness") or "UNKNOWN")
    data_quality = str(state.get("data_quality") or "UNKNOWN")
    policy_state = str(policy.get("policy_state") or "UNKNOWN")
    reserve_status = str((policy.get("reserve_policy") or {}).get("status") or "UNKNOWN")
    debt_blocking = bool((policy.get("debt_policy") or {}).get("investment_blocking"))
    speculative = _decimal(
        (allocation.get("bucket_totals") or {}).get("speculative_capital")
    ) or Decimal("0.00")
    protected = _decimal(
        (allocation.get("bucket_totals") or {}).get("protected_capital")
    )

    reasons = [
        "REAL_TRADING_NOT_SUPPORTED",
        "SPECULATIVE_CAPITAL_NOT_AUTHORIZED",
        "TRADING_DISPATCH_DISABLED",
    ]
    if readiness != "READY":
        reasons.append(f"INVESTMENT_READINESS_{readiness}")
    if data_quality not in {"COMPLETE", "SUFFICIENT"}:
        reasons.append(f"FINANCIAL_DATA_{data_quality}")
    if debt_blocking:
        reasons.append("PRIORITY_DEBT")
    if reserve_status in {"ABSENT", "BUILDING", "UNKNOWN"}:
        reasons.append(f"EMERGENCY_RESERVE_{reserve_status}")
    if plan.get("trading_dispatch") is not False:
        reasons.append("INVALID_TRADING_DISPATCH_STATE")

    financial_blocked = (
        readiness == "BLOCKED"
        or data_quality in {"INSUFFICIENT", "UNSAFE", "STALE"}
        or debt_blocking
        or reserve_status == "ABSENT"
    )
    status = "DATA_BLOCKED" if financial_blocked else "PAPER_ONLY"
    financial_status = f"{policy_state}:{readiness}"
    return TradingRiskBudgetRead(
        paper_simulation_allowed=True,
        financial_status=financial_status,
        risk_budget_status=status,
        protected_capital=protected,
        blocking_reasons=list(dict.fromkeys(reasons)),
        context_fingerprints=_fingerprints(plan, context, continuous),
        household_id=household_id,
        simulation_rules={
            "quote_asset": DEFAULT_CONFIG.quote_asset,
            "max_open_positions": DEFAULT_CONFIG.max_open_positions,
            "max_position_fraction": str(DEFAULT_CONFIG.max_position_size),
            "max_capital_per_trade_fraction": str(
                DEFAULT_CONFIG.max_capital_per_trade
            ),
            "max_daily_loss_fraction": str(DEFAULT_CONFIG.max_daily_loss),
            "minimum_model_confidence": str(DEFAULT_CONFIG.min_confidence),
            "rules_apply_to_virtual_balance_only": True,
        },
    )


async def current_trading_risk_budget(
    session: AsyncSession, *, household_id: int, user_id: int
) -> TradingRiskBudgetRead:
    plan, context = await action_plan_service.current_action_plan_source_context(
        session, household_id=household_id, user_id=user_id
    )
    continuous = await continuous_service.current_continuous_autopilot(
        session, household_id=household_id, user_id=user_id
    )
    return build_risk_budget(
        household_id=household_id,
        plan=plan,
        context=context,
        continuous=continuous,
    )
