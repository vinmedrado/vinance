from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial_policy.engine import calculate_financial_policy
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


async def current_financial_policy(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the current canonical State once and derive a read-only policy."""

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
    return calculate_financial_policy(
        current_state,
        normalized_inputs=normalized_inputs,
        previous_financial_state=previous_state,
    )


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
