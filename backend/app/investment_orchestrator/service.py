from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.capital_allocation import service as allocation_service
from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.financial_policy import service as policy_service
from backend.app.financial_state import service as state_service
from backend.app.investment_orchestrator.context import (
    load_market_context,
    load_portfolio_context,
    load_profile_context,
)
from backend.app.investment_orchestrator.engine import (
    calculate_investment_orchestration,
    decision_fingerprint_from_payload,
)
from backend.app.investment_orchestrator.models import InvestmentOrchestrationDecision
from backend.app.investment_orchestrator.rules import ENGINE_VERSION, RULES_VERSION


def _canonical_json(value: Any) -> str:
    return json.dumps(
        jsonable_encoder(value, custom_encoder={Decimal: str}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _json_value(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _market_not_consulted(*, reason: str, captured_at: datetime) -> dict[str, Any]:
    return {
        "captured_at": captured_at,
        "status": "NOT_CONSULTED",
        "markets": [],
        "candidates": [],
        "partial_failures": [],
        "missing_information": [],
        "sources": {},
        "reason": reason,
    }


async def _evaluate(
    session: AsyncSession,
    *,
    state: Mapping[str, Any],
    policy: Mapping[str, Any],
    allocation: Mapping[str, Any],
    normalized_inputs: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    profile_context = await load_profile_context(
        session, normalized_inputs=normalized_inputs
    )
    portfolio_context = await load_portfolio_context(
        session, normalized_inputs=normalized_inputs
    )
    investment_budget = Decimal(
        str(allocation.get("investment_bucket_amount") or "0")
    )
    readiness = policy.get("investment_readiness")
    if investment_budget <= 0:
        market_context = _market_not_consulted(
            reason="investment_bucket_not_positive", captured_at=generated_at
        )
    elif readiness == "BLOCKED":
        market_context = _market_not_consulted(
            reason="investment_readiness_blocked", captured_at=generated_at
        )
    elif profile_context.get("effective_profile") is None:
        market_context = _market_not_consulted(
            reason="investor_profile_missing_or_inconsistent",
            captured_at=generated_at,
        )
    else:
        market_context = await load_market_context(
            session,
            investment_budget=investment_budget,
            profile=profile_context["effective_profile"],
            captured_at=generated_at,
        )
    try:
        return calculate_investment_orchestration(
            state,
            policy,
            allocation,
            profile_context=profile_context,
            portfolio_context=portfolio_context,
            market_context=market_context,
            generated_at=generated_at,
        )
    except (AssertionError, ValueError) as exc:
        raise state_service.FinancialStateValidationError(str(exc)) from exc


async def current_investment_orchestration(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the live A1 -> A4 chain without persisting any decision."""

    (
        state,
        policy,
        normalized_inputs,
    ) = await policy_service.current_financial_policy_source_context(
        session,
        household_id=household_id,
        user_id=user_id,
        evaluated_at=evaluated_at,
    )
    allocation = calculate_capital_allocation(state, policy)
    return await _evaluate(
        session,
        state=state,
        policy=policy,
        allocation=allocation,
        normalized_inputs=normalized_inputs,
        generated_at=evaluated_at,
    )


async def _chain_from_allocation(
    session: AsyncSession,
    *,
    household_id: int,
    allocation_id: int,
    user_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    allocation = await allocation_service.get_capital_allocation_decision(
        session,
        household_id=household_id,
        allocation_id=allocation_id,
        user_id=user_id,
    )
    policy_id = allocation.get("financial_policy_id")
    state_id = allocation.get("financial_state_snapshot_id")
    if policy_id is None or state_id is None:
        raise state_service.FinancialStateValidationError(
            "frozen Capital Allocation has no complete State -> Policy chain"
        )
    policy = await policy_service.get_policy_decision(
        session,
        household_id=household_id,
        policy_id=int(policy_id),
        user_id=user_id,
    )
    snapshot = await state_service.get_snapshot(
        session,
        household_id=household_id,
        snapshot_id=int(state_id),
        user_id=user_id,
    )
    state = policy_service._state_from_snapshot(snapshot)
    if int(policy.get("financial_state_snapshot_id")) != int(state_id):
        raise state_service.FinancialStateValidationError(
            "Capital Allocation chain references divergent Financial State snapshots"
        )
    if int(allocation.get("financial_policy_id")) != int(policy.get("policy_id")):
        raise state_service.FinancialStateValidationError(
            "Capital Allocation chain references a divergent Financial Policy"
        )
    return state, policy, allocation, dict(snapshot.normalized_inputs)


async def investment_orchestration_from_allocation_decision(
    session: AsyncSession,
    *,
    household_id: int,
    allocation_id: int,
    user_id: int,
) -> dict[str, Any]:
    state, policy, allocation, normalized_inputs = await _chain_from_allocation(
        session,
        household_id=household_id,
        allocation_id=allocation_id,
        user_id=user_id,
    )
    return await _evaluate(
        session,
        state=state,
        policy=policy,
        allocation=allocation,
        normalized_inputs=normalized_inputs,
    )


def _decision_read(decision: InvestmentOrchestrationDecision) -> dict[str, Any]:
    """Return the exact frozen decision; historical reads never touch live markets."""

    payload = deepcopy(dict(decision.decision_payload))
    indexed_contract = {
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_decision_id": decision.financial_policy_decision_id,
        "capital_allocation_decision_id": decision.capital_allocation_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "status": decision.status,
        "currency": decision.currency,
        "investment_budget": decision.investment_budget,
        "suggested_capital": decision.suggested_capital,
        "remaining_investment_cash": decision.remaining_investment_cash,
        "speculative_capital": decision.speculative_capital,
        "state_fingerprint": decision.state_fingerprint,
        "policy_fingerprint": decision.policy_fingerprint,
        "allocation_fingerprint": decision.allocation_fingerprint,
        "market_context_fingerprint": decision.market_context_fingerprint,
        "ruleset_fingerprint": decision.ruleset_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
    }
    for field, expected in indexed_contract.items():
        if _canonical_json(payload.get(field)) != _canonical_json(expected):
            raise state_service.FinancialStateValidationError(
                f"stored investment orchestration failed the immutable contract check: {field}"
            )
    if decision_fingerprint_from_payload(payload) != decision.decision_fingerprint:
        raise state_service.FinancialStateValidationError(
            "stored investment orchestration failed the immutable payload fingerprint check"
        )
    payload.update(
        {
            "orchestration_id": decision.id,
            "generated_at": decision.generated_at,
            "created_at": decision.created_at,
        }
    )
    return payload


def _decision_summary(decision: InvestmentOrchestrationDecision) -> dict[str, Any]:
    return {
        "orchestration_id": decision.id,
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_decision_id": decision.financial_policy_decision_id,
        "capital_allocation_decision_id": decision.capital_allocation_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "status": decision.status,
        "currency": decision.currency,
        "investment_budget": decision.investment_budget,
        "suggested_capital": decision.suggested_capital,
        "remaining_investment_cash": decision.remaining_investment_cash,
        "decision_fingerprint": decision.decision_fingerprint,
        "generated_at": decision.generated_at,
        "created_at": decision.created_at,
    }


async def _decision_by_idempotency(
    session: AsyncSession,
    *,
    household_id: int,
    idempotency_key: str,
) -> InvestmentOrchestrationDecision | None:
    result = await session.execute(
        select(InvestmentOrchestrationDecision).where(
            InvestmentOrchestrationDecision.household_id == household_id,
            InvestmentOrchestrationDecision.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _decision_by_allocation(
    session: AsyncSession,
    *,
    allocation_id: int,
) -> InvestmentOrchestrationDecision | None:
    result = await session.execute(
        select(InvestmentOrchestrationDecision).where(
            InvestmentOrchestrationDecision.capital_allocation_decision_id
            == allocation_id,
            InvestmentOrchestrationDecision.engine_version == ENGINE_VERSION,
            InvestmentOrchestrationDecision.rules_version == RULES_VERSION,
        )
    )
    return result.scalar_one_or_none()


async def create_investment_orchestration_decision(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Freeze one immutable A1 -> A2 -> A3 -> A4 decision chain."""

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

    allocation_key = (
        "investment-orchestrator-v1:"
        + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        if idempotency_key
        else None
    )
    allocation = await allocation_service.create_capital_allocation_decision(
        session,
        household_id=household_id,
        user_id=user_id,
        idempotency_key=allocation_key,
    )
    allocation_id = int(allocation["allocation_id"])
    existing_for_allocation = await _decision_by_allocation(
        session, allocation_id=allocation_id
    )
    if existing_for_allocation is not None:
        return _decision_read(existing_for_allocation)

    state, policy, allocation, normalized_inputs = await _chain_from_allocation(
        session,
        household_id=household_id,
        allocation_id=allocation_id,
        user_id=user_id,
    )
    orchestration = await _evaluate(
        session,
        state=state,
        policy=policy,
        allocation=allocation,
        normalized_inputs=normalized_inputs,
    )
    payload = _json_value(orchestration)
    decision = InvestmentOrchestrationDecision(
        household_id=household_id,
        financial_state_snapshot_id=int(orchestration["financial_state_snapshot_id"]),
        financial_policy_decision_id=int(
            orchestration["financial_policy_decision_id"]
        ),
        capital_allocation_decision_id=int(
            orchestration["capital_allocation_decision_id"]
        ),
        created_by_user_id=user_id,
        engine_version=orchestration["engine_version"],
        rules_version=orchestration["rules_version"],
        status=orchestration["status"],
        currency=orchestration["currency"],
        investment_budget=orchestration["investment_budget"],
        suggested_capital=orchestration["suggested_capital"],
        remaining_investment_cash=orchestration["remaining_investment_cash"],
        speculative_capital=orchestration["speculative_capital"],
        state_fingerprint=orchestration["state_fingerprint"],
        policy_fingerprint=orchestration["policy_fingerprint"],
        allocation_fingerprint=orchestration["allocation_fingerprint"],
        market_context_fingerprint=orchestration["market_context_fingerprint"],
        ruleset_fingerprint=orchestration["ruleset_fingerprint"],
        decision_fingerprint=orchestration["decision_fingerprint"],
        decision_payload=payload,
        idempotency_key=idempotency_key,
        generated_at=orchestration["generated_at"],
    )
    session.add(decision)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        concurrent: InvestmentOrchestrationDecision | None = None
        if idempotency_key:
            concurrent = await _decision_by_idempotency(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
            )
        if concurrent is None:
            concurrent = await _decision_by_allocation(
                session, allocation_id=allocation_id
            )
        if concurrent is None:
            raise
        return _decision_read(concurrent)
    await session.refresh(decision)
    return _decision_read(decision)


async def investment_orchestration_history(
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
        select(func.count(InvestmentOrchestrationDecision.id)).where(
            InvestmentOrchestrationDecision.household_id == household_id
        )
    )
    result = await session.execute(
        select(InvestmentOrchestrationDecision)
        .where(InvestmentOrchestrationDecision.household_id == household_id)
        .order_by(
            InvestmentOrchestrationDecision.generated_at.desc(),
            InvestmentOrchestrationDecision.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [_decision_summary(item) for item in result.scalars().all()],
        "total": int(total_result.scalar_one()),
    }


async def get_investment_orchestration_decision(
    session: AsyncSession,
    *,
    household_id: int,
    orchestration_id: int,
    user_id: int,
) -> dict[str, Any]:
    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(InvestmentOrchestrationDecision).where(
            InvestmentOrchestrationDecision.id == orchestration_id,
            InvestmentOrchestrationDecision.household_id == household_id,
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise state_service.FinancialResourceNotFoundError(
            "investment orchestration decision not found"
        )
    return _decision_read(decision)
