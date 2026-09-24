from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.action_plan.engine import (
    calculate_action_plan,
    decision_fingerprint_from_payload,
)
from backend.app.action_plan.models import ActionPlanDecision
from backend.app.action_plan.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.financial_policy import service as policy_service
from backend.app.financial_state import service as state_service
from backend.app.investment_orchestrator import service as orchestration_service


def _canonical_json(value: Any) -> str:
    return json.dumps(
        jsonable_encoder(value, custom_encoder={Decimal: str}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _json_value(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _calculate(
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    allocation: Mapping[str, Any],
    orchestration: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        return calculate_action_plan(state, policy, allocation, orchestration)
    except (AssertionError, ValueError) as exc:
        raise state_service.FinancialStateValidationError(str(exc)) from exc


async def current_action_plan(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the live A1 -> A5 chain without persisting it."""

    state, policy, normalized_inputs = (
        await policy_service.current_financial_policy_source_context(
            session,
            household_id=household_id,
            user_id=user_id,
            evaluated_at=evaluated_at,
        )
    )
    allocation = calculate_capital_allocation(state, policy)
    orchestration = await orchestration_service._evaluate(
        session,
        state=state,
        policy=policy,
        allocation=allocation,
        normalized_inputs=normalized_inputs,
        generated_at=evaluated_at,
    )
    return _calculate(state, policy, allocation, orchestration)


async def _chain_from_orchestration(
    session: AsyncSession,
    *,
    household_id: int,
    orchestration_id: int,
    user_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    orchestration = await orchestration_service.get_investment_orchestration_decision(
        session,
        household_id=household_id,
        orchestration_id=orchestration_id,
        user_id=user_id,
    )
    allocation_id = orchestration.get("capital_allocation_decision_id")
    if allocation_id is None:
        raise state_service.FinancialStateValidationError(
            "frozen Investment Orchestration has no complete A1 -> A4 chain"
        )
    state, policy, allocation, _ = await orchestration_service._chain_from_allocation(
        session,
        household_id=household_id,
        allocation_id=int(allocation_id),
        user_id=user_id,
    )
    if orchestration.get("financial_state_snapshot_id") != state.get("snapshot_id"):
        raise state_service.FinancialStateValidationError(
            "Investment Orchestration references a divergent Financial State"
        )
    if orchestration.get("financial_policy_decision_id") != policy.get("policy_id"):
        raise state_service.FinancialStateValidationError(
            "Investment Orchestration references a divergent Financial Policy"
        )
    if orchestration.get("capital_allocation_decision_id") != allocation.get(
        "allocation_id"
    ):
        raise state_service.FinancialStateValidationError(
            "Investment Orchestration references a divergent Capital Allocation"
        )
    return state, policy, allocation, orchestration


async def action_plan_from_orchestration_decision(
    session: AsyncSession,
    *,
    household_id: int,
    orchestration_id: int,
    user_id: int,
) -> dict[str, Any]:
    state, policy, allocation, orchestration = await _chain_from_orchestration(
        session,
        household_id=household_id,
        orchestration_id=orchestration_id,
        user_id=user_id,
    )
    return _calculate(state, policy, allocation, orchestration)


def _decision_read(decision: ActionPlanDecision) -> dict[str, Any]:
    """Return the frozen payload after validating its indexed immutable contract."""

    payload = deepcopy(dict(decision.decision_payload))
    summary = payload.get("summary") or {}
    indexed_contract = {
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_decision_id": decision.financial_policy_decision_id,
        "capital_allocation_decision_id": decision.capital_allocation_decision_id,
        "investment_orchestration_decision_id": decision.investment_orchestration_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "status": decision.status,
        "currency": decision.currency,
        "period": decision.period,
        "total_financial_actions": decision.total_financial_actions,
        "total_investment_actions": decision.total_investment_actions,
        "total_hold_cash": decision.total_hold_cash,
        "speculative_capital": decision.speculative_capital,
        "state_fingerprint": decision.state_fingerprint,
        "policy_fingerprint": decision.policy_fingerprint,
        "allocation_fingerprint": decision.allocation_fingerprint,
        "orchestration_fingerprint": decision.orchestration_fingerprint,
        "ruleset_fingerprint": decision.ruleset_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
    }
    for field, expected in indexed_contract.items():
        if _canonical_json(payload.get(field)) != _canonical_json(expected):
            raise state_service.FinancialStateValidationError(
                f"stored Action Plan failed the immutable contract check: {field}"
            )
    summary_contract = {
        "authorized_financial_capital": decision.authorized_financial_capital,
        "authorized_investment_capital": decision.investment_budget,
        "investment_buy_total": decision.total_investment_actions,
        "hold_cash_total": decision.total_hold_cash,
    }
    for field, expected in summary_contract.items():
        if _canonical_json(summary.get(field)) != _canonical_json(expected):
            raise state_service.FinancialStateValidationError(
                f"stored Action Plan failed the immutable summary check: {field}"
            )
    if decision_fingerprint_from_payload(payload) != decision.decision_fingerprint:
        raise state_service.FinancialStateValidationError(
            "stored Action Plan failed the immutable payload fingerprint check"
        )
    payload.update(
        {
            "action_plan_id": decision.id,
            "generated_at": decision.generated_at,
            "created_at": decision.created_at,
        }
    )
    return payload


def _decision_summary(decision: ActionPlanDecision) -> dict[str, Any]:
    payload = _decision_read(decision)
    summary = payload.get("summary") or {}
    actions = payload.get("actions") or []
    return {
        "action_plan_id": decision.id,
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_decision_id": decision.financial_policy_decision_id,
        "capital_allocation_decision_id": decision.capital_allocation_decision_id,
        "investment_orchestration_decision_id": decision.investment_orchestration_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "status": decision.status,
        "currency": decision.currency,
        "period": decision.period,
        "primary_action": summary.get("primary_action"),
        "action_titles": [
            str(item.get("title"))
            for item in actions[:3]
            if isinstance(item, Mapping) and item.get("title")
        ],
        "action_count": int(summary.get("action_count") or len(actions)),
        "investment_budget": decision.investment_budget,
        "total_financial_actions": decision.total_financial_actions,
        "total_investment_actions": decision.total_investment_actions,
        "total_hold_cash": decision.total_hold_cash,
        "decision_fingerprint": decision.decision_fingerprint,
        "generated_at": decision.generated_at,
        "created_at": decision.created_at,
    }


async def _decision_by_idempotency(
    session: AsyncSession, *, household_id: int, idempotency_key: str
) -> ActionPlanDecision | None:
    result = await session.execute(
        select(ActionPlanDecision).where(
            ActionPlanDecision.household_id == household_id,
            ActionPlanDecision.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _decision_by_orchestration(
    session: AsyncSession, *, orchestration_id: int
) -> ActionPlanDecision | None:
    result = await session.execute(
        select(ActionPlanDecision).where(
            ActionPlanDecision.investment_orchestration_decision_id
            == orchestration_id,
            ActionPlanDecision.engine_version == ENGINE_VERSION,
            ActionPlanDecision.rules_version == RULES_VERSION,
        )
    )
    return result.scalar_one_or_none()


async def create_action_plan_decision(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Freeze one immutable A1 -> A5 decision chain."""

    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    if idempotency_key:
        existing = await _decision_by_idempotency(
            session,
            household_id=household_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return _decision_read(existing)

    orchestration_key = (
        "action-plan-v1:"
        + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        if idempotency_key
        else None
    )
    orchestration = (
        await orchestration_service.create_investment_orchestration_decision(
            session,
            household_id=household_id,
            user_id=user_id,
            idempotency_key=orchestration_key,
        )
    )
    orchestration_id = int(orchestration["orchestration_id"])
    existing_for_orchestration = await _decision_by_orchestration(
        session, orchestration_id=orchestration_id
    )
    if existing_for_orchestration is not None:
        return _decision_read(existing_for_orchestration)

    state, policy, allocation, orchestration = await _chain_from_orchestration(
        session,
        household_id=household_id,
        orchestration_id=orchestration_id,
        user_id=user_id,
    )
    plan = _calculate(state, policy, allocation, orchestration)
    payload = _json_value(plan)
    summary = plan["summary"]
    if (
        plan.get("currency") is None
        or plan.get("period") is None
        or summary.get("authorized_financial_capital") is None
        or orchestration.get("investment_budget") is None
        or orchestration.get("suggested_capital") is None
        or orchestration.get("remaining_investment_cash") is None
        or plan.get("policy_fingerprint") is None
        or plan.get("allocation_fingerprint") is None
        or plan.get("orchestration_fingerprint") is None
    ):
        raise state_service.FinancialStateValidationError(
            "a frozen Action Plan requires a complete monetary chain"
        )
    decision = ActionPlanDecision(
        household_id=household_id,
        financial_state_snapshot_id=int(plan["financial_state_snapshot_id"]),
        financial_policy_decision_id=int(plan["financial_policy_decision_id"]),
        capital_allocation_decision_id=int(plan["capital_allocation_decision_id"]),
        investment_orchestration_decision_id=int(
            plan["investment_orchestration_decision_id"]
        ),
        created_by_user_id=user_id,
        engine_version=plan["engine_version"],
        rules_version=plan["rules_version"],
        status=plan["status"],
        currency=plan["currency"],
        period=plan["period"],
        authorized_financial_capital=summary["authorized_financial_capital"],
        investment_budget=orchestration["investment_budget"],
        suggested_capital=orchestration["suggested_capital"],
        remaining_investment_cash=orchestration["remaining_investment_cash"],
        total_financial_actions=plan["total_financial_actions"],
        total_investment_actions=plan["total_investment_actions"],
        total_hold_cash=plan["total_hold_cash"],
        speculative_capital=plan["speculative_capital"],
        state_fingerprint=plan["state_fingerprint"],
        policy_fingerprint=plan["policy_fingerprint"],
        allocation_fingerprint=plan["allocation_fingerprint"],
        orchestration_fingerprint=plan["orchestration_fingerprint"],
        ruleset_fingerprint=plan["ruleset_fingerprint"],
        decision_fingerprint=plan["decision_fingerprint"],
        decision_payload=payload,
        idempotency_key=idempotency_key,
        generated_at=plan["generated_at"],
    )
    session.add(decision)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        concurrent: ActionPlanDecision | None = None
        if idempotency_key:
            concurrent = await _decision_by_idempotency(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
            )
        if concurrent is None:
            concurrent = await _decision_by_orchestration(
                session, orchestration_id=orchestration_id
            )
        if concurrent is None:
            raise
        return _decision_read(concurrent)
    await session.refresh(decision)
    return _decision_read(decision)


async def action_plan_history(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    total_result = await session.execute(
        select(func.count(ActionPlanDecision.id)).where(
            ActionPlanDecision.household_id == household_id
        )
    )
    result = await session.execute(
        select(ActionPlanDecision)
        .where(ActionPlanDecision.household_id == household_id)
        .order_by(ActionPlanDecision.generated_at.desc(), ActionPlanDecision.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [_decision_summary(item) for item in result.scalars().all()],
        "total": int(total_result.scalar_one()),
    }


async def get_action_plan_decision(
    session: AsyncSession,
    *,
    household_id: int,
    action_plan_id: int,
    user_id: int,
) -> dict[str, Any]:
    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(ActionPlanDecision).where(
            ActionPlanDecision.id == action_plan_id,
            ActionPlanDecision.household_id == household_id,
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise state_service.FinancialResourceNotFoundError(
            "action plan decision not found"
        )
    return _decision_read(decision)
