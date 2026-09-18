from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_policy.models import FinancialPolicyDecision
from backend.app.financial_policy.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.financial_state import service as state_service
from backend.app.financial_state.engine import (
    ENGINE_VERSION as FINANCIAL_STATE_ENGINE_VERSION,
    calculate_financial_state,
)
from backend.app.financial_state.models import FinancialStateSnapshot


def _canonical_json(value: Any) -> str:
    return json.dumps(
        jsonable_encoder(value, custom_encoder={Decimal: str}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _snapshot_input_fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    """Round-trip through the canonical encoder before writing JSON columns."""

    return json.loads(_canonical_json(value))


def _state_from_snapshot(snapshot: FinancialStateSnapshot) -> dict[str, Any]:
    if snapshot.engine_version != FINANCIAL_STATE_ENGINE_VERSION:
        raise state_service.FinancialStateValidationError(
            "snapshot uses an unsupported financial state engine version"
        )
    normalized_inputs = dict(snapshot.normalized_inputs)
    if _snapshot_input_fingerprint(normalized_inputs) != snapshot.input_fingerprint:
        raise state_service.FinancialStateValidationError(
            "snapshot normalized inputs failed the integrity check"
        )
    state = calculate_financial_state(
        normalized_inputs,
        evaluated_at=snapshot.evaluated_at,
    )
    persisted_contract = {
        "household_id": snapshot.household_id,
        "engine_version": snapshot.engine_version,
        "metrics": snapshot.metrics,
        "member_views": snapshot.member_views,
        "data_quality": snapshot.data_quality,
        "confidence": snapshot.confidence,
        "missing_fields": snapshot.missing_fields,
        "inconsistencies": snapshot.inconsistencies,
    }
    rebuilt_contract = {
        key: state[key]
        for key in persisted_contract
    }
    if _canonical_json(rebuilt_contract) != _canonical_json(persisted_contract):
        raise state_service.FinancialStateValidationError(
            "snapshot state failed the immutable contract check"
        )
    state["snapshot_id"] = snapshot.id
    return state


async def _previous_snapshot(
    session: AsyncSession,
    *,
    household_id: int,
    before_evaluated_at: datetime,
    before_snapshot_id: int | None = None,
) -> FinancialStateSnapshot | None:
    before = FinancialStateSnapshot.evaluated_at < before_evaluated_at
    if before_snapshot_id is not None:
        before = or_(
            before,
            and_(
                FinancialStateSnapshot.evaluated_at == before_evaluated_at,
                FinancialStateSnapshot.id < before_snapshot_id,
            ),
        )
    result = await session.execute(
        select(FinancialStateSnapshot)
        .where(
            FinancialStateSnapshot.household_id == household_id,
            FinancialStateSnapshot.engine_version == FINANCIAL_STATE_ENGINE_VERSION,
            before,
        )
        .order_by(
            FinancialStateSnapshot.evaluated_at.desc(),
            FinancialStateSnapshot.id.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def current_financial_policy_context(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate State exactly once and return it with its derived Policy.

    The paired contract is consumed by later Autopilot stages so they cannot
    accidentally evaluate a second, slightly different Financial State.
    """

    evaluated = evaluated_at or datetime.now(timezone.utc)
    normalized_inputs = await state_service.build_normalized_inputs(
        session,
        household_id=household_id,
        user_id=user_id,
    )
    current_state = calculate_financial_state(
        normalized_inputs,
        evaluated_at=evaluated,
    )
    snapshot = await _previous_snapshot(
        session,
        household_id=household_id,
        before_evaluated_at=current_state["evaluated_at"],
    )
    previous_state = _state_from_snapshot(snapshot) if snapshot is not None else None
    policy = calculate_financial_policy(
        current_state,
        normalized_inputs=normalized_inputs,
        previous_financial_state=previous_state,
    )
    return current_state, policy


async def current_financial_policy(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the current canonical State once and derive a read-only policy."""

    _, policy = await current_financial_policy_context(
        session,
        household_id=household_id,
        user_id=user_id,
        evaluated_at=evaluated_at,
    )
    return policy


async def financial_policy_from_state_snapshot(
    session: AsyncSession,
    *,
    household_id: int,
    snapshot_id: int,
    user_id: int,
) -> dict[str, Any]:
    """Replay policy-v1 from an immutable Financial State v1 snapshot."""

    snapshot = await state_service.get_snapshot(
        session,
        household_id=household_id,
        snapshot_id=snapshot_id,
        user_id=user_id,
    )
    source_state = _state_from_snapshot(snapshot)
    previous_snapshot = await _previous_snapshot(
        session,
        household_id=household_id,
        before_evaluated_at=snapshot.evaluated_at,
        before_snapshot_id=snapshot.id,
    )
    previous_state = (
        _state_from_snapshot(previous_snapshot)
        if previous_snapshot is not None
        else None
    )
    return calculate_financial_policy(
        source_state,
        normalized_inputs=dict(snapshot.normalized_inputs),
        previous_financial_state=previous_state,
    )


def _decision_read(decision: FinancialPolicyDecision) -> dict[str, Any]:
    """Return the exact frozen payload; historical reads never rerun an engine."""

    payload = deepcopy(dict(decision.decision_payload))
    indexed_contract = {
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "policy_state": decision.policy_state,
        "investment_readiness": decision.investment_readiness,
        "input_fingerprint": decision.input_fingerprint,
        "ruleset_fingerprint": decision.ruleset_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
    }
    for field, expected in indexed_contract.items():
        if payload.get(field) != expected:
            raise state_service.FinancialStateValidationError(
                f"stored policy decision failed the immutable contract check: {field}"
            )
    payload.update(
        {
            "policy_id": decision.id,
            "financial_state_snapshot_id": decision.financial_state_snapshot_id,
            "generated_at": decision.generated_at,
            "created_at": decision.created_at,
        }
    )
    return payload


def _decision_summary(decision: FinancialPolicyDecision) -> dict[str, Any]:
    return {
        "policy_id": decision.id,
        "household_id": decision.household_id,
        "financial_state_snapshot_id": decision.financial_state_snapshot_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "policy_state": decision.policy_state,
        "investment_readiness": decision.investment_readiness,
        "decision_fingerprint": decision.decision_fingerprint,
        "generated_at": decision.generated_at,
        "created_at": decision.created_at,
    }


async def _decision_by_idempotency(
    session: AsyncSession,
    *,
    household_id: int,
    idempotency_key: str,
) -> FinancialPolicyDecision | None:
    result = await session.execute(
        select(FinancialPolicyDecision).where(
            FinancialPolicyDecision.household_id == household_id,
            FinancialPolicyDecision.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def create_policy_decision(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Freeze policy-v1 against a newly captured immutable State v1 snapshot."""

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

    snapshot_key = (
        "financial-policy-v1:"
        + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        if idempotency_key
        else None
    )
    snapshot = await state_service.create_snapshot(
        session,
        household_id=household_id,
        user_id=user_id,
        idempotency_key=snapshot_key,
    )
    policy = await financial_policy_from_state_snapshot(
        session,
        household_id=household_id,
        snapshot_id=snapshot.id,
        user_id=user_id,
    )
    policy_payload = _json_value(policy)
    decision = FinancialPolicyDecision(
        household_id=household_id,
        financial_state_snapshot_id=snapshot.id,
        created_by_user_id=user_id,
        engine_version=policy["engine_version"],
        rules_version=policy["rules_version"],
        policy_state=policy["policy_state"],
        investment_readiness=policy["investment_readiness"],
        input_fingerprint=policy["input_fingerprint"],
        ruleset_fingerprint=policy["ruleset_fingerprint"],
        decision_fingerprint=policy["decision_fingerprint"],
        decision_payload=policy_payload,
        idempotency_key=idempotency_key,
        generated_at=snapshot.evaluated_at,
    )
    session.add(decision)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        concurrent: FinancialPolicyDecision | None = None
        if idempotency_key:
            concurrent = await _decision_by_idempotency(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
            )
        if concurrent is None:
            result = await session.execute(
                select(FinancialPolicyDecision).where(
                    FinancialPolicyDecision.financial_state_snapshot_id == snapshot.id,
                    FinancialPolicyDecision.engine_version == ENGINE_VERSION,
                    FinancialPolicyDecision.rules_version == RULES_VERSION,
                )
            )
            concurrent = result.scalar_one_or_none()
        if concurrent is None:
            raise
        return _decision_read(concurrent)
    await session.refresh(decision)
    return _decision_read(decision)


async def policy_decision_history(
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
        select(func.count(FinancialPolicyDecision.id)).where(
            FinancialPolicyDecision.household_id == household_id
        )
    )
    result = await session.execute(
        select(FinancialPolicyDecision)
        .where(FinancialPolicyDecision.household_id == household_id)
        .order_by(
            FinancialPolicyDecision.generated_at.desc(),
            FinancialPolicyDecision.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [_decision_summary(item) for item in result.scalars().all()],
        "total": int(total_result.scalar_one()),
    }


async def get_policy_decision(
    session: AsyncSession,
    *,
    household_id: int,
    policy_id: int,
    user_id: int,
) -> dict[str, Any]:
    await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(FinancialPolicyDecision).where(
            FinancialPolicyDecision.id == policy_id,
            FinancialPolicyDecision.household_id == household_id,
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise state_service.FinancialResourceNotFoundError(
            "financial policy decision not found"
        )
    return _decision_read(decision)
