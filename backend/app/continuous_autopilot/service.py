from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from typing import Any, Mapping, Sequence

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.action_plan import service as action_plan_service
from backend.app.action_plan.models import ActionPlanDecision
from backend.app.continuous_autopilot.alerts import deliver_continuous_alert
from backend.app.continuous_autopilot.engine import (
    calculate_continuous_autopilot,
    decision_fingerprint_from_payload,
)
from backend.app.continuous_autopilot.models import (
    ContinuousAutopilotDecision,
    ContinuousAutopilotRequest,
    ContinuousAutopilotState,
)
from backend.app.continuous_autopilot.privacy import project_decision_for_user
from backend.app.continuous_autopilot.rules import (
    CHANGE_CATEGORIES,
    ENGINE_VERSION,
    MANUAL_FAILED_RETRY_COOLDOWN_SECONDS,
    RULESET_FINGERPRINT,
    RULES_VERSION,
    reevaluation_scope,
)
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import Household, HouseholdMember
from backend.app.investment_orchestrator import service as orchestration_service


class ContinuousAutopilotConflictError(state_service.FinancialStateDomainError):
    """The same idempotency key was reused for different evaluation inputs."""


class ContinuousAutopilotUnavailableError(state_service.FinancialStateDomainError):
    """A technical dependency prevented a safe reevaluation."""


class ContinuousAutopilotCooldownError(state_service.FinancialStateDomainError):
    """A recent failed manual evaluation is inside its bounded retry window."""

    def __init__(self, *, retry_after: int):
        super().__init__("continuous evaluation retry cooldown is active")
        self.retry_after = max(1, retry_after)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _manual_retry_after(
    state: ContinuousAutopilotState, *, evaluated_at: datetime
) -> int | None:
    if state.status != "FAILED" or state.last_evaluated_at is None:
        return None
    failed_at = state.last_evaluated_at
    if failed_at.tzinfo is None:
        failed_at = failed_at.replace(tzinfo=timezone.utc)
    current = evaluated_at
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    retry_at = failed_at.astimezone(timezone.utc) + timedelta(
        seconds=MANUAL_FAILED_RETRY_COOLDOWN_SECONDS
    )
    remaining = (retry_at - current.astimezone(timezone.utc)).total_seconds()
    return max(1, ceil(remaining)) if remaining > 0 else None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        jsonable_encoder(value, custom_encoder={Decimal: str}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _json_value(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _request_fingerprint(
    *, household_id: int, as_of: datetime | None, change_categories: Sequence[str]
) -> str:
    explicit_time = as_of
    if explicit_time is not None:
        if explicit_time.tzinfo is None:
            explicit_time = explicit_time.replace(tzinfo=timezone.utc)
        explicit_time = explicit_time.astimezone(timezone.utc)
    identity = {
        "household_id": household_id,
        "mode": "INTERNAL" if explicit_time is not None or change_categories else "MANUAL",
        "as_of": explicit_time,
        "change_categories": sorted(
            {
                str(item).upper()
                for item in change_categories
                if str(item).upper() in CHANGE_CATEGORIES
            }
        ),
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _validate_idempotent_replay(
    stored_request_fingerprint: str, *, request_fingerprint: str
) -> None:
    if stored_request_fingerprint != request_fingerprint:
        raise ContinuousAutopilotConflictError(
            "Idempotency-Key already belongs to a different evaluation request"
        )


async def _decision_by_idempotency(
    session: AsyncSession, *, household_id: int, idempotency_key: str
) -> tuple[ContinuousAutopilotDecision, str] | None:
    request = await session.get(
        ContinuousAutopilotRequest,
        (household_id, idempotency_key),
    )
    if request is None:
        return None
    decision = await session.get(
        ContinuousAutopilotDecision, request.continuous_decision_id
    )
    if decision is None or decision.household_id != household_id:
        raise state_service.FinancialStateValidationError(
            "continuous autopilot request points to an invalid decision"
        )
    return decision, request.request_fingerprint


async def _bind_idempotency_request(
    session: AsyncSession,
    *,
    household_id: int,
    idempotency_key: str,
    request_fingerprint: str,
    decision_id: int,
) -> None:
    session.add(
        ContinuousAutopilotRequest(
            household_id=household_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            continuous_decision_id=decision_id,
        )
    )
    await session.flush()


async def _decision_by_fingerprint(
    session: AsyncSession, *, household_id: int, fingerprint: str
) -> ContinuousAutopilotDecision | None:
    result = await session.execute(
        select(ContinuousAutopilotDecision).where(
            ContinuousAutopilotDecision.household_id == household_id,
            ContinuousAutopilotDecision.decision_fingerprint == fingerprint,
        )
    )
    return result.scalar_one_or_none()


def _decision_read(decision: ContinuousAutopilotDecision) -> dict[str, Any]:
    payload = deepcopy(dict(decision.decision_payload))
    indexed = {
        "household_id": decision.household_id,
        "previous_action_plan_id": decision.previous_action_plan_id,
        "current_action_plan_id": decision.current_action_plan_id,
        "engine_version": decision.engine_version,
        "rules_version": decision.rules_version,
        "status": decision.status,
        "materiality": decision.materiality,
        "alert_decision": decision.alert_decision,
        "reevaluation_scope": decision.reevaluation_scope,
        "previous_fingerprint": decision.previous_fingerprint,
        "current_fingerprint": decision.current_fingerprint,
        "ruleset_fingerprint": decision.ruleset_fingerprint,
        "decision_fingerprint": decision.decision_fingerprint,
        "dedupe_key": decision.dedupe_key,
    }
    for field, expected in indexed.items():
        if _canonical_json(payload.get(field)) != _canonical_json(expected):
            raise state_service.FinancialStateValidationError(
                f"stored Continuous Autopilot decision failed immutable contract: {field}"
            )
    if decision_fingerprint_from_payload(payload) != decision.decision_fingerprint:
        raise state_service.FinancialStateValidationError(
            "stored Continuous Autopilot payload fingerprint is invalid"
        )
    payload.update(
        {
            "continuous_decision_id": decision.id,
            "created_at": decision.created_at,
            "generated_at": decision.generated_at,
            "observed_at": decision.observed_at,
        }
    )
    return payload


def _shared_household_access(access: Any) -> bool:
    if access is None:
        return False
    try:
        household = access[0]
    except (KeyError, IndexError, TypeError):
        household = getattr(access, "household", None)
    return str(getattr(household, "household_type", "")).upper() == "SHARED"


def _decision_summary(
    decision: ContinuousAutopilotDecision,
    *,
    user_id: int,
    shared_household: bool,
) -> dict[str, Any]:
    payload = project_decision_for_user(
        _decision_read(decision),
        user_id=user_id,
        shared_household=shared_household,
    )
    alert = payload.get("alert") or {}
    return {
        "continuous_decision_id": decision.id,
        "household_id": decision.household_id,
        "previous_action_plan_id": decision.previous_action_plan_id,
        "current_action_plan_id": decision.current_action_plan_id,
        "status": payload["status"],
        "materiality": payload["materiality"],
        "alert_decision": payload["alert_decision"],
        "title": alert.get("title") or (
            "Seu plano está atualizado"
            if payload["status"] in {"UP_TO_DATE", "UNCHANGED"}
            else "Avaliação do Autopilot"
        ),
        "summary": alert.get("summary")
        or (payload.get("plan_diff") or {}).get("summary")
        or "Avaliação concluída.",
        "change_count": len(payload.get("detected_changes") or []),
        "decision_fingerprint": decision.decision_fingerprint,
        "observed_at": decision.observed_at,
        "generated_at": decision.generated_at,
        "created_at": decision.created_at,
    }


async def _latest_action_plan(
    session: AsyncSession,
    *,
    household_id: int,
    action_plan_id: int | None = None,
) -> ActionPlanDecision | None:
    query = select(ActionPlanDecision).where(
        ActionPlanDecision.household_id == household_id
    )
    if action_plan_id is not None:
        query = query.where(ActionPlanDecision.id == action_plan_id)
    else:
        query = query.order_by(
            ActionPlanDecision.generated_at.desc(), ActionPlanDecision.id.desc()
        ).limit(1)
    result = await session.execute(query)
    plan = result.scalar_one_or_none()
    if action_plan_id is not None and plan is None:
        raise state_service.FinancialStateValidationError(
            "the monitored Action Plan no longer belongs to this household"
        )
    return plan


def _with_operational_state(
    payload: Mapping[str, Any], state: ContinuousAutopilotState | None
) -> dict[str, Any]:
    result = deepcopy(dict(payload))
    result["operational_status"] = state.status if state is not None else None
    result["pending_categories"] = list(
        state.pending_categories or [] if state is not None else []
    )
    result["last_evaluated_at"] = (
        state.last_evaluated_at if state is not None else None
    )
    result["last_successful_at"] = (
        state.last_successful_at if state is not None else None
    )
    result["operational_warnings"] = (
        [
            {
                "code": "LAST_EVALUATION_FAILED",
                "message": (
                    "A última tentativa falhou; o último plano válido foi preservado."
                ),
                "fields": [],
                "rule_ids": [],
            }
        ]
        if state is not None and state.status == "FAILED"
        else []
    )
    return result


async def _decision_with_current_operational_state(
    session: AsyncSession,
    decision: ContinuousAutopilotDecision,
    *,
    state: ContinuousAutopilotState | None = None,
) -> dict[str, Any]:
    operational = state
    if operational is None:
        operational = await session.get(
            ContinuousAutopilotState, decision.household_id
        )
    return _with_operational_state(_decision_read(decision), operational)


def _alert_episode_for_result(
    state: ContinuousAutopilotState, result: Mapping[str, Any]
) -> int | None:
    alert = result.get("alert")
    alert_decision = str(result.get("alert_decision") or "NO_ALERT")
    if alert_decision in {"NO_ALERT", "INFORMATIONAL"} or not isinstance(
        alert, Mapping
    ):
        state.active_alert_key = None
        return None
    active_key = str(
        alert.get("dedupe_key") or result.get("decision_fingerprint") or ""
    )
    if not active_key:
        state.active_alert_key = None
        return None
    if getattr(state, "active_alert_key", None) != active_key:
        state.alert_episode = int(getattr(state, "alert_episode", 0) or 0) + 1
        state.active_alert_key = active_key
    return int(getattr(state, "alert_episode", 0) or 0)


async def _latest_decision(
    session: AsyncSession, *, household_id: int
) -> ContinuousAutopilotDecision | None:
    result = await session.execute(
        select(ContinuousAutopilotDecision)
        .where(ContinuousAutopilotDecision.household_id == household_id)
        .order_by(
            ContinuousAutopilotDecision.generated_at.desc(),
            ContinuousAutopilotDecision.id.desc(),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _state_for_update(
    session: AsyncSession, *, household_id: int
) -> ContinuousAutopilotState:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(select(func.pg_advisory_xact_lock(620_006, household_id)))
    result = await session.execute(
        select(ContinuousAutopilotState)
        .where(ContinuousAutopilotState.household_id == household_id)
        .with_for_update()
    )
    state = result.scalar_one_or_none()
    if state is None:
        state = ContinuousAutopilotState(
            household_id=household_id,
            status="REEVALUATION_REQUIRED",
            pending_categories=["HOUSEHOLD"],
            dirty_since=_now(),
        )
        session.add(state)
        await session.flush()
    return state


async def mark_household_dirty(
    session: AsyncSession,
    *,
    household_id: int,
    category: str,
    dirty_at: datetime | None = None,
) -> None:
    """Mark an input mutation in the caller's transaction; never commits."""

    normalized = category.upper()
    if normalized not in CHANGE_CATEGORIES:
        raise ValueError(f"unknown Continuous Autopilot category: {category}")
    result = await session.execute(
        select(ContinuousAutopilotState)
        .where(ContinuousAutopilotState.household_id == household_id)
        .with_for_update()
    )
    state = result.scalar_one_or_none()
    if state is None:
        session.add(
            ContinuousAutopilotState(
                household_id=household_id,
                status="REEVALUATION_REQUIRED",
                pending_categories=[normalized],
                dirty_since=dirty_at or _now(),
            )
        )
        return
    state.pending_categories = sorted(
        set(state.pending_categories or []) | {normalized}
    )
    state.status = "REEVALUATION_REQUIRED"
    state.dirty_since = state.dirty_since or dirty_at or _now()
    state.last_error_code = None


async def mark_user_households_dirty(
    session: AsyncSession,
    *,
    user_id: int,
    category: str,
    dirty_at: datetime | None = None,
) -> None:
    result = await session.execute(
        select(HouseholdMember.household_id).where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
        )
    )
    for household_id in sorted({int(value) for value in result.scalars().all()}):
        await mark_household_dirty(
            session,
            household_id=household_id,
            category=category,
            dirty_at=dirty_at,
        )


def _empty_current(
    *, household_id: int, state: ContinuousAutopilotState | None, observed_at: datetime
) -> dict[str, Any]:
    status = state.status if state else "REEVALUATION_REQUIRED"
    fingerprint = hashlib.sha256(
        f"continuous-autopilot-empty:{household_id}:{status}".encode("utf-8")
    ).hexdigest()
    return {
        "continuous_decision_id": None,
        "household_id": household_id,
        "previous_action_plan_id": None,
        "current_action_plan_id": None,
        "engine_version": ENGINE_VERSION,
        "rules_version": RULES_VERSION,
        "status": status,
        "materiality": "NONE",
        "alert_decision": "NO_ALERT",
        "reevaluation_scope": reevaluation_scope(
            state.pending_categories if state else ["HOUSEHOLD"]
        ),
        "change_categories": list(state.pending_categories if state else ["HOUSEHOLD"]),
        "detected_changes": [],
        "plan_diff": {
            "previous_action_plan_id": None,
            "current_action_plan_id": None,
            "added_actions": [],
            "removed_actions": [],
            "changed_actions": [],
            "unchanged_actions": [],
            "financial_delta": "0.00",
            "investment_delta": "0.00",
            "hold_cash_delta": "0.00",
            "priority_changes": [],
            "status_change": None,
            "materiality": "NONE",
            "summary": "Uma avaliação inicial ainda é necessária.",
        },
        "alert": None,
        "blockers": [],
        "warnings": [],
        "missing_information": [],
        "evidence": [],
        "rule_traces": [],
        "ruleset": {},
        "previous_fingerprint": None,
        "current_fingerprint": None,
        "ruleset_fingerprint": RULESET_FINGERPRINT,
        "decision_fingerprint": fingerprint,
        "dedupe_key": fingerprint,
        "generated_at": observed_at,
        "observed_at": observed_at,
        "created_at": None,
        "operational_status": status,
        "pending_categories": list(
            state.pending_categories if state else ["HOUSEHOLD"]
        ),
        "last_evaluated_at": state.last_evaluated_at if state else None,
        "last_successful_at": state.last_successful_at if state else None,
        "operational_warnings": [],
    }


async def current_continuous_autopilot(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    access = await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    state = await session.get(ContinuousAutopilotState, household_id)
    current: ContinuousAutopilotDecision | None = None
    if state is not None and state.last_continuous_decision_id is not None:
        current = await session.get(
            ContinuousAutopilotDecision, state.last_continuous_decision_id
        )
        if current is None or current.household_id != household_id:
            raise state_service.FinancialStateValidationError(
                "continuous autopilot state points to an invalid decision"
            )
    elif state is None:
        # Backward-compatible fallback for a decision created before the
        # operational state row existed.  New schema always seeds the state.
        current = await _latest_decision(session, household_id=household_id)
    if current is None:
        return project_decision_for_user(
            _empty_current(
                household_id=household_id,
                state=state,
                observed_at=observed_at or _now(),
            ),
            user_id=user_id,
            shared_household=_shared_household_access(access),
        )
    return project_decision_for_user(
        _with_operational_state(_decision_read(current), state),
        user_id=user_id,
        shared_household=_shared_household_access(access),
    )


async def _evaluate_continuous_autopilot(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str,
    as_of: datetime | None = None,
    change_categories: Sequence[str] = (),
    access_checked: bool = False,
) -> dict[str, Any]:
    if not access_checked:
        await state_service.get_household_access(
            session, household_id=household_id, user_id=user_id
        )
    request_fingerprint = _request_fingerprint(
        household_id=household_id,
        as_of=as_of,
        change_categories=change_categories,
    )
    existing = await _decision_by_idempotency(
        session, household_id=household_id, idempotency_key=idempotency_key
    )
    if existing is not None:
        existing_decision, stored_request_fingerprint = existing
        _validate_idempotent_replay(
            stored_request_fingerprint, request_fingerprint=request_fingerprint
        )
        return await _decision_with_current_operational_state(
            session, existing_decision
        )

    evaluated_at = as_of or _now()
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
    operational = await _state_for_update(session, household_id=household_id)
    existing = await _decision_by_idempotency(
        session, household_id=household_id, idempotency_key=idempotency_key
    )
    if existing is not None:
        existing_decision, stored_request_fingerprint = existing
        _validate_idempotent_replay(
            stored_request_fingerprint, request_fingerprint=request_fingerprint
        )
        return await _decision_with_current_operational_state(
            session, existing_decision, state=operational
        )

    # Public manual evaluations with fresh keys must not hammer the complete
    # chain while a persistent dependency failure is still cooling down.
    # Exact idempotent replays return above and internal scheduled evaluations
    # always carry an explicit as_of/categories, so neither is rate-limited.
    if (
        as_of is None
        and not change_categories
    ):
        retry_after = _manual_retry_after(
            operational, evaluated_at=evaluated_at
        )
        if retry_after is not None:
            await session.rollback()
            raise ContinuousAutopilotCooldownError(retry_after=retry_after)

    # A clean manual request is a cheap status check. Internal Celery/test calls
    # always provide explicit time/categories and continue through the engine.
    if (
        as_of is None
        and not change_categories
        and not operational.pending_categories
        and operational.status
        in {"UP_TO_DATE", "UNCHANGED", "CHANGED", "BLOCKED"}
        and operational.last_continuous_decision_id is not None
    ):
        current = await session.get(
            ContinuousAutopilotDecision,
            operational.last_continuous_decision_id,
        )
        if current is not None and current.household_id == household_id:
            await _bind_idempotency_request(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                decision_id=current.id,
            )
            await session.commit()
            return _with_operational_state(_decision_read(current), operational)

    categories = sorted(
        {
            *(str(item).upper() for item in operational.pending_categories or []),
            *(str(item).upper() for item in change_categories),
        }
        & set(CHANGE_CATEGORIES)
    )
    if not categories:
        categories = ["FRESHNESS"]
    scope = reevaluation_scope(categories)
    baseline_evaluation_count = operational.evaluation_count
    baseline_last_successful_at = operational.last_successful_at
    operational.status = "EVALUATING"
    operational.evaluation_count += 1
    baseline_continuous_decision_id = operational.last_continuous_decision_id
    await session.flush()

    final_fingerprint: str | None = None
    try:
        previous_row = await _latest_action_plan(
            session,
            household_id=household_id,
            action_plan_id=operational.last_action_plan_id,
        )
        previous = (
            action_plan_service._decision_read(previous_row)
            if previous_row is not None
            else None
        )
        previous_context: dict[str, Any] | None = None
        if previous is not None:
            previous_state, previous_policy, previous_allocation, previous_orchestration = (
                await action_plan_service._chain_from_orchestration(
                    session,
                    household_id=household_id,
                    orchestration_id=int(
                        previous["investment_orchestration_decision_id"]
                    ),
                    user_id=user_id,
                )
            )
            previous_context = {
                "state": previous_state,
                "policy": previous_policy,
                "allocation": previous_allocation,
                "orchestration": previous_orchestration,
            }
        if scope == "INVESTMENT_CHAIN" and previous is not None:
            live, live_context = (
                await action_plan_service.action_plan_from_allocation_source_context(
                    session,
                    household_id=household_id,
                    allocation_id=int(previous["capital_allocation_decision_id"]),
                    user_id=user_id,
                    evaluated_at=evaluated_at,
                )
            )
        else:
            live, live_context = (
                await action_plan_service.current_action_plan_source_context(
                    session,
                    household_id=household_id,
                    user_id=user_id,
                    evaluated_at=evaluated_at,
                )
            )
        preliminary = calculate_continuous_autopilot(
            previous,
            live,
            as_of=evaluated_at,
            observed_at=evaluated_at,
            change_categories=categories,
            reevaluation_scope=scope,
            previous_context=previous_context,
            current_context=live_context,
        )
        should_freeze = previous is None or preliminary["materiality"] in {
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }
        if should_freeze:
            chain_digest = hashlib.sha256(
                _canonical_json(
                    {
                        "household_id": household_id,
                        "live_fingerprint": live.get("decision_fingerprint"),
                        "as_of": evaluated_at,
                        "rules": RULES_VERSION,
                    }
                ).encode("utf-8")
            ).hexdigest()
            if scope == "INVESTMENT_CHAIN" and previous is not None:
                orchestration = (
                    await orchestration_service.create_investment_orchestration_from_allocation_decision(
                        session,
                        household_id=household_id,
                        allocation_id=int(previous["capital_allocation_decision_id"]),
                        user_id=user_id,
                        idempotency_key=(
                            "continuous-autopilot-investment:" + chain_digest
                        ),
                        evaluated_at=evaluated_at,
                        commit=False,
                    )
                )
                current = (
                    await action_plan_service.create_action_plan_from_orchestration_decision(
                        session,
                        household_id=household_id,
                        orchestration_id=int(orchestration["orchestration_id"]),
                        user_id=user_id,
                        idempotency_key=("continuous-autopilot-action:" + chain_digest),
                        commit=False,
                    )
                )
            else:
                current = await action_plan_service.create_action_plan_decision(
                    session,
                    household_id=household_id,
                    user_id=user_id,
                    idempotency_key=("continuous-autopilot-chain:" + chain_digest),
                    evaluated_at=evaluated_at,
                    commit=False,
                )
        else:
            assert previous is not None
            current = previous

        result = calculate_continuous_autopilot(
            previous,
            current,
            as_of=evaluated_at,
            observed_at=evaluated_at,
            change_categories=categories,
            reevaluation_scope=scope,
            previous_context=previous_context,
            current_context=live_context,
        )
        final_fingerprint = result["decision_fingerprint"]
        duplicate = await _decision_by_fingerprint(
            session,
            household_id=household_id,
            fingerprint=result["decision_fingerprint"],
        )
        if duplicate is not None:
            await _bind_idempotency_request(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                decision_id=duplicate.id,
            )
            alert_episode = _alert_episode_for_result(operational, result)
            alert_count = 0
            if alert_episode is not None:
                alert_count = await deliver_continuous_alert(
                    session,
                    continuous_decision_id=duplicate.id,
                    household_id=household_id,
                    payload=result,
                    alert_episode=alert_episode,
                )
            operational.status = duplicate.status
            operational.pending_categories = []
            operational.dirty_since = None
            operational.last_evaluated_at = evaluated_at
            operational.last_successful_at = evaluated_at
            operational.last_error_code = None
            operational.last_action_plan_id = duplicate.current_action_plan_id
            operational.last_continuous_decision_id = duplicate.id
            operational.change_count += int(duplicate.materiality != "NONE")
            operational.no_change_count += int(duplicate.materiality == "NONE")
            operational.alert_count += alert_count
            await session.commit()
            return _with_operational_state(_decision_read(duplicate), operational)

        payload = _json_value(result)
        decision = ContinuousAutopilotDecision(
            household_id=household_id,
            previous_action_plan_id=result["previous_action_plan_id"],
            current_action_plan_id=int(result["current_action_plan_id"]),
            created_by_user_id=user_id,
            engine_version=result["engine_version"],
            rules_version=result["rules_version"],
            status=result["status"],
            materiality=result["materiality"],
            alert_decision=result["alert_decision"],
            reevaluation_scope=result["reevaluation_scope"],
            change_count=len(result["detected_changes"]),
            decision_payload=payload,
            previous_fingerprint=result["previous_fingerprint"],
            current_fingerprint=result["current_fingerprint"],
            ruleset_fingerprint=result["ruleset_fingerprint"],
            decision_fingerprint=result["decision_fingerprint"],
            dedupe_key=result["dedupe_key"],
            observed_at=result["observed_at"],
            generated_at=result["generated_at"],
        )
        session.add(decision)
        await session.flush()
        await _bind_idempotency_request(
            session,
            household_id=household_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            decision_id=decision.id,
        )
        alert_episode = _alert_episode_for_result(operational, result)
        alert_count = 0
        if alert_episode is not None:
            alert_count = await deliver_continuous_alert(
                session,
                continuous_decision_id=decision.id,
                household_id=household_id,
                payload=result,
                alert_episode=alert_episode,
            )
        operational.status = result["status"]
        operational.pending_categories = []
        operational.dirty_since = None
        operational.last_evaluated_at = evaluated_at
        operational.last_successful_at = evaluated_at
        operational.last_error_code = None
        operational.last_action_plan_id = decision.current_action_plan_id
        operational.last_continuous_decision_id = decision.id
        operational.change_count += int(result["materiality"] != "NONE")
        operational.no_change_count += int(result["materiality"] == "NONE")
        operational.alert_count += alert_count
        await session.commit()
        await session.refresh(decision)
        return _with_operational_state(_decision_read(decision), operational)
    except IntegrityError as exc:
        await session.rollback()
        recovered_state = await _state_for_update(
            session, household_id=household_id
        )
        replay = await _decision_by_idempotency(
            session, household_id=household_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            concurrent, stored_request_fingerprint = replay
            _validate_idempotent_replay(
                stored_request_fingerprint,
                request_fingerprint=request_fingerprint,
            )
            response = _with_operational_state(
                _decision_read(concurrent), recovered_state
            )
            await session.rollback()
            return response
        concurrent = None
        if final_fingerprint is not None:
            concurrent = await _decision_by_fingerprint(
                session,
                household_id=household_id,
                fingerprint=final_fingerprint,
            )
        if concurrent is None:
            await session.rollback()
            raise ContinuousAutopilotUnavailableError(
                "continuous evaluation conflicted without a committed winner"
            ) from exc
        await _bind_idempotency_request(
            session,
            household_id=household_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            decision_id=concurrent.id,
        )
        await session.commit()
        return _with_operational_state(
            _decision_read(concurrent), recovered_state
        )
    except Exception as exc:
        await session.rollback()
        try:
            failed = await _state_for_update(session, household_id=household_id)
            replay = await _decision_by_idempotency(
                session,
                household_id=household_id,
                idempotency_key=idempotency_key,
            )
            if replay is not None:
                concurrent, stored_request_fingerprint = replay
                _validate_idempotent_replay(
                    stored_request_fingerprint,
                    request_fingerprint=request_fingerprint,
                )
                response = _with_operational_state(
                    _decision_read(concurrent), failed
                )
                await session.rollback()
                return response
            # A concurrent winner may legitimately deduplicate to the same
            # immutable decision id.  The operational evaluation counter and
            # success timestamp therefore form part of the success revision.
            concurrent_success = (
                (
                    failed.last_continuous_decision_id is not None
                    and failed.last_continuous_decision_id
                    != baseline_continuous_decision_id
                )
                or failed.evaluation_count > baseline_evaluation_count
                or (
                    failed.last_successful_at is not None
                    and failed.last_successful_at != baseline_last_successful_at
                )
            )
            if not concurrent_success:
                failed.status = "FAILED"
                failed.last_evaluated_at = evaluated_at
                failed.last_error_code = type(exc).__name__[:80]
                failed.failure_count += 1
                await session.commit()
            else:
                await session.rollback()
        except state_service.FinancialStateDomainError:
            await session.rollback()
            raise
        except Exception:
            # Failure bookkeeping is best-effort.  Never mask the provider or
            # database error that caused this evaluation to fail.
            try:
                await session.rollback()
            except Exception:
                pass
        if isinstance(exc, state_service.FinancialStateDomainError):
            raise
        raise ContinuousAutopilotUnavailableError(
            "continuous evaluation could not produce a safe decision"
        ) from exc


async def evaluate_continuous_autopilot(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str,
    as_of: datetime | None = None,
    change_categories: Sequence[str] = (),
    project_for_user: bool = True,
) -> dict[str, Any]:
    """Public boundary that consistently maps technical failures to 503."""

    try:
        access = None
        if project_for_user:
            access = await state_service.get_household_access(
                session, household_id=household_id, user_id=user_id
            )
        result = await _evaluate_continuous_autopilot(
            session,
            household_id=household_id,
            user_id=user_id,
            idempotency_key=idempotency_key,
            as_of=as_of,
            change_categories=change_categories,
            access_checked=project_for_user,
        )
        if not project_for_user:
            return result
        return project_decision_for_user(
            result,
            user_id=user_id,
            shared_household=_shared_household_access(access),
        )
    except state_service.FinancialStateDomainError:
        raise
    except Exception as exc:
        try:
            await session.rollback()
        except Exception:
            pass
        raise ContinuousAutopilotUnavailableError(
            "continuous evaluation could not produce a safe decision"
        ) from exc


async def continuous_autopilot_history(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    access = await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    total_result = await session.execute(
        select(func.count(ContinuousAutopilotDecision.id)).where(
            ContinuousAutopilotDecision.household_id == household_id
        )
    )
    result = await session.execute(
        select(ContinuousAutopilotDecision)
        .where(ContinuousAutopilotDecision.household_id == household_id)
        .order_by(
            ContinuousAutopilotDecision.generated_at.desc(),
            ContinuousAutopilotDecision.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [
            _decision_summary(
                item,
                user_id=user_id,
                shared_household=_shared_household_access(access),
            )
            for item in result.scalars().all()
        ],
        "total": int(total_result.scalar_one()),
    }


async def get_continuous_autopilot_decision(
    session: AsyncSession,
    *,
    household_id: int,
    continuous_decision_id: int,
    user_id: int,
) -> dict[str, Any]:
    access = await state_service.get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(ContinuousAutopilotDecision).where(
            ContinuousAutopilotDecision.id == continuous_decision_id,
            ContinuousAutopilotDecision.household_id == household_id,
        )
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise state_service.FinancialResourceNotFoundError(
            "continuous autopilot decision not found"
        )
    return project_decision_for_user(
        _decision_read(decision),
        user_id=user_id,
        shared_household=_shared_household_access(access),
    )


async def scheduled_households(
    session: AsyncSession, *, limit: int
) -> list[tuple[int, int, list[str]]]:
    owner = (
        select(
            HouseholdMember.household_id.label("household_id"),
            func.min(HouseholdMember.user_id).label("user_id"),
        )
        .where(
            HouseholdMember.status == "ACTIVE",
            HouseholdMember.role == "OWNER",
        )
        .group_by(HouseholdMember.household_id)
        .subquery()
    )
    result = await session.execute(
        select(
            ContinuousAutopilotState.household_id,
            owner.c.user_id,
            ContinuousAutopilotState.pending_categories,
        )
        .join(owner, owner.c.household_id == ContinuousAutopilotState.household_id)
        .join(Household, Household.id == ContinuousAutopilotState.household_id)
        .where(Household.status == "ACTIVE")
        .order_by(
            (ContinuousAutopilotState.status == "REEVALUATION_REQUIRED").desc(),
            ContinuousAutopilotState.last_evaluated_at.asc().nullsfirst(),
            ContinuousAutopilotState.household_id.asc(),
        )
        .limit(limit)
    )
    return [
        (int(household_id), int(user_id), list(categories or []))
        for household_id, user_id, categories in result.all()
    ]


async def operational_alert_count(
    session: AsyncSession, *, household_id: int
) -> int:
    result = await session.execute(
        select(ContinuousAutopilotState.alert_count).where(
            ContinuousAutopilotState.household_id == household_id
        )
    )
    return int(result.scalar_one_or_none() or 0)
