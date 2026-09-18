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

from backend.app.capital_allocation.engine import (
    calculate_capital_allocation,
    decision_fingerprint_from_payload,
)
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.capital_allocation.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.financial_policy import service as policy_service
from backend.app.financial_state import service as state_service


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
    state: Mapping[str, Any], policy: Mapping[str, Any]
) -> dict[str, Any]:
    try:
        return calculate_capital_allocation(state, policy)
    except (AssertionError, ValueError) as exc:
        raise state_service.FinancialStateValidationError(str(exc)) from exc


async def current_capital_allocation(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Derive a read-only allocation from one paired current State + Policy."""

    state, policy = await policy_service.current_financial_policy_context(
        session,
        household_id=household_id,
        user_id=user_id,
        evaluated_at=evaluated_at,
    )
    return _calculate(state, policy)


async def _state_for_policy(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    snapshot_id = policy.get("financial_state_snapshot_id")
    if snapshot_id is None:
        raise state_service.FinancialStateValidationError(
            "frozen financial policy has no Financial State snapshot"
        )
    snapshot = await state_service.get_snapshot(
        session,
        household_id=household_id,
        snapshot_id=int(snapshot_id),
        user_id=user_id,
    )
    return policy_service._state_from_snapshot(snapshot)


async def capital_allocation_from_policy_decision(
    session: AsyncSession,
    *,
    household_id: int,
    policy_id: int,
    user_id: int,
) -> dict[str, Any]:
    """Replay allocation-v1 from an exact immutable State -> Policy chain."""

    policy = await policy_service.get_policy_decision(
        session,
        household_id=household_id,
        policy_id=policy_id,
        user_id=user_id,
    )
    state = await _state_for_policy(
        session,
        household_id=household_id,
        user_id=user_id,
        policy=policy,
    )
    return _calculate(state, policy)


def _decision_read(decision: CapitalAllocationDecision) -> dict[str, Any]:
    """Return the exact frozen output; historical reads never rerun engines."""

    payload = deepcopy(dict(decision.decision_payload))
    indexed_contract = {
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_id": decision.financial_policy_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "allocation_period": decision.allocation_period,
        "allocation_status": decision.allocation_status,
        "currency": decision.currency,
        "allocatable_capital": decision.allocatable_capital,
        "allocated_capital": decision.allocated_capital,
        "remaining_capital": decision.remaining_capital,
        "investment_bucket_amount": decision.investment_bucket_amount,
        "input_fingerprint": decision.input_fingerprint,
        "policy_fingerprint": decision.policy_fingerprint,
        "ruleset_fingerprint": decision.ruleset_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
    }
    for field, expected in indexed_contract.items():
        if _canonical_json(payload.get(field)) != _canonical_json(expected):
            raise state_service.FinancialStateValidationError(
                f"stored capital allocation failed the immutable contract check: {field}"
            )
    if decision_fingerprint_from_payload(payload) != decision.decision_fingerprint:
        raise state_service.FinancialStateValidationError(
            "stored capital allocation failed the immutable payload fingerprint check"
        )
    payload.update(
        {
            "allocation_id": decision.id,
            "financial_state_snapshot_id": decision.financial_state_snapshot_id,
            "financial_policy_id": decision.financial_policy_decision_id,
            "generated_at": decision.generated_at,
            "created_at": decision.created_at,
        }
    )
    return payload


def _decision_summary(decision: CapitalAllocationDecision) -> dict[str, Any]:
    return {
        "allocation_id": decision.id,
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "financial_policy_id": decision.financial_policy_decision_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "allocation_period": decision.allocation_period,
        "allocation_status": decision.allocation_status,
        "currency": decision.currency,
        "allocatable_capital": decision.allocatable_capital,
        "allocated_capital": decision.allocated_capital,
        "investment_bucket_amount": decision.investment_bucket_amount,
        "decision_fingerprint": decision.decision_fingerprint,
        "generated_at": decision.generated_at,
        "created_at": decision.created_at,
    }


async def _decision_by_idempotency(
    session: AsyncSession,
    *,
    household_id: int,
    idempotency_key: str,
) -> CapitalAllocationDecision | None:
    result = await session.execute(
        select(CapitalAllocationDecision).where(
            CapitalAllocationDecision.household_id == household_id,
            CapitalAllocationDecision.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _decision_by_policy(
    session: AsyncSession,
    *,
    policy_id: int,
) -> CapitalAllocationDecision | None:
    result = await session.execute(
        select(CapitalAllocationDecision).where(
            CapitalAllocationDecision.financial_policy_decision_id == policy_id,
            CapitalAllocationDecision.engine_version == ENGINE_VERSION,
            CapitalAllocationDecision.rules_version == RULES_VERSION,
        )
    )
    return result.scalar_one_or_none()


async def create_capital_allocation_decision(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Freeze one immutable State -> Policy -> Allocation decision chain."""

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

    policy_key = (
        "capital-allocation-v1:"
        + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        if idempotency_key
        else None
    )
    policy = await policy_service.create_policy_decision(
        session,
        household_id=household_id,
        user_id=user_id,
        idempotency_key=policy_key,
    )
    policy_id = int(policy["policy_id"])
    if idempotency_key:
        existing_for_policy = await _decision_by_policy(session, policy_id=policy_id)
        if existing_for_policy is not None:
            return _decision_read(existing_for_policy)
    state = await _state_for_policy(
        session,
        household_id=household_id,
        user_id=user_id,
        policy=policy,
    )
    allocation = _calculate(state, policy)
    payload = _json_value(allocation)
    decision = CapitalAllocationDecision(
        household_id=household_id,
        financial_state_snapshot_id=int(allocation["financial_state_snapshot_id"]),
        financial_policy_decision_id=policy_id,
        created_by_user_id=user_id,
        engine_version=allocation["engine_version"],
        rules_version=allocation["rules_version"],
        allocation_period=allocation["allocation_period"],
        allocation_status=allocation["allocation_status"],
        currency=allocation["currency"],
        allocatable_capital=allocation["allocatable_capital"],
        allocated_capital=allocation["allocated_capital"],
        remaining_capital=allocation["remaining_capital"],
        investment_bucket_amount=allocation["investment_bucket_amount"],
        input_fingerprint=allocation["input_fingerprint"],
        policy_fingerprint=allocation["policy_fingerprint"],
        ruleset_fingerprint=allocation["ruleset_fingerprint"],
        decision_fingerprint=allocation["decision_fingerprint"],
        decision_payload=payload,
        idempotency_key=idempotency_key,
        generated_at=allocation["generated_at"],
    )
    session.add(decision)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        concurrent: CapitalAllocationDecision | None = None
        if idempotency_key:
            concurrent = await _decision_by_idempotency(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
            )
        if concurrent is None:
            concurrent = await _decision_by_policy(session, policy_id=policy_id)
        if concurrent is None:
            raise
        return _decision_read(concurrent)
    await session.refresh(decision)
    return _decision_read(decision)


async def capital_allocation_history(
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
        select(func.count(CapitalAllocationDecision.id)).where(
            CapitalAllocationDecision.household_id == household_id
        )
    )
    result = await session.execute(
        select(CapitalAllocationDecision)
        .where(CapitalAllocationDecision.household_id == household_id)
        .order_by(
            CapitalAllocationDecision.generated_at.desc(),
            CapitalAllocationDecision.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [_decision_summary(item) for item in result.scalars().all()],
        "total": int(total_result.scalar_one()),
    }


async def get_capital_allocation_decision(
    session: AsyncSession,
    *,
    household_id: int,
    allocation_id: int,
    user_id: int,
) -> dict[str, Any]:
    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(CapitalAllocationDecision).where(
            CapitalAllocationDecision.id == allocation_id,
            CapitalAllocationDecision.household_id == household_id,
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise state_service.FinancialResourceNotFoundError(
            "capital allocation decision not found"
        )
    return _decision_read(decision)
