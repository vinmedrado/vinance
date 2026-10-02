from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.app.action_plan import service as action_plan_service
from backend.app.continuous_autopilot import service
from backend.app.continuous_autopilot.models import ContinuousAutopilotDecision
from backend.app.financial_state import service as state_service
from backend.tests.test_autopilot_continuous_engine import NOW, _evaluate, _plan


class _ScalarResult:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values or []

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.values


class _Session:
    def __init__(self, results=None, get_value=None):
        self.results = list(results or [])
        self.get_value = get_value
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.queries = []

    async def execute(self, _query):
        self.queries.append(_query)
        return self.results.pop(0)

    async def get(self, _model, _key):
        return self.get_value

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

    def add(self, item):
        self.added.append(item)

    async def flush(self):
        for item in self.added:
            if isinstance(item, ContinuousAutopilotDecision) and item.id is None:
                item.id = 51
                item.created_at = NOW

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, item):
        if isinstance(item, ContinuousAutopilotDecision):
            item.id = 51
            item.created_at = NOW


def _stored_decision(payload: dict | None = None) -> SimpleNamespace:
    payload = payload or _evaluate(None, _plan(plan_id=42))
    return SimpleNamespace(
        id=51,
        household_id=10,
        previous_action_plan_id=payload["previous_action_plan_id"],
        current_action_plan_id=payload["current_action_plan_id"],
        created_by_user_id=91,
        engine_version=payload["engine_version"],
        rules_version=payload["rules_version"],
        status=payload["status"],
        materiality=payload["materiality"],
        alert_decision=payload["alert_decision"],
        reevaluation_scope=payload["reevaluation_scope"],
        change_count=len(payload["detected_changes"]),
        decision_payload=service._json_value(payload),
        previous_fingerprint=payload["previous_fingerprint"],
        current_fingerprint=payload["current_fingerprint"],
        ruleset_fingerprint=payload["ruleset_fingerprint"],
        decision_fingerprint=payload["decision_fingerprint"],
        dedupe_key=payload["dedupe_key"],
        observed_at=NOW,
        generated_at=NOW,
        created_at=NOW,
    )


def _operational(**values):
    defaults = {
        "household_id": 10,
        "status": "REEVALUATION_REQUIRED",
        "pending_categories": ["FINANCIAL_DATA"],
        "dirty_since": NOW,
        "last_evaluated_at": None,
        "last_successful_at": None,
        "last_error_code": None,
        "last_action_plan_id": None,
        "last_continuous_decision_id": None,
        "evaluation_count": 0,
        "change_count": 0,
        "alert_count": 0,
        "no_change_count": 0,
        "failure_count": 0,
        "active_alert_key": None,
        "alert_episode": 0,
    }
    defaults.update(values)
    return SimpleNamespace(**defaults)


def _mixed_private_payload() -> dict:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    previous["actions"][1]["owner_user_id"] = 92
    previous["actions"][1]["description"] = "SEGREDO_92_ANTES"
    current["actions"][1].update(
        {
            "owner_user_id": 92,
            "action_type": "INVESTMENT_AVOID",
            "action_status": "AVOID",
            "description": "SEGREDO_92_DEPOIS",
        }
    )
    current["actions"][0]["amount"] = "700.00"
    current["total_financial_actions"] = "700.00"
    current["decision_fingerprint"] = "b" * 64
    return _evaluate(previous, current)


def test_historical_read_uses_frozen_payload_and_detects_tampering() -> None:
    decision = _stored_decision()
    assert service._decision_read(decision)["continuous_decision_id"] == 51
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload["materiality"] = "CRITICAL"
    with pytest.raises(state_service.FinancialStateValidationError, match="immutable"):
        service._decision_read(decision)


@pytest.mark.asyncio
async def test_idempotent_retry_returns_before_recalculation(monkeypatch) -> None:
    decision = _stored_decision()
    operational = _operational(
        status="REEVALUATION_REQUIRED",
        pending_categories=["MARKET_DATA"],
        last_action_plan_id=decision.current_action_plan_id,
        last_continuous_decision_id=decision.id,
        evaluation_count=4,
    )
    session = _Session(get_value=operational)

    async def access(*_args, **_kwargs):
        return None

    async def existing(*_args, **_kwargs):
        return (
            decision,
            service._request_fingerprint(
                household_id=10, as_of=NOW, change_categories=()
            ),
        )

    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("idempotent retry must not evaluate A1-A5")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    monkeypatch.setattr(action_plan_service, "current_action_plan", must_not_run)
    result = await service.evaluate_continuous_autopilot(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="request-1",
        as_of=NOW,
    )
    assert result["continuous_decision_id"] == 51
    assert result["operational_status"] == "REEVALUATION_REQUIRED"
    assert result["pending_categories"] == ["MARKET_DATA"]
    assert operational.evaluation_count == 4
    assert session.commits == 0


@pytest.mark.asyncio
async def test_no_change_does_not_create_duplicate_a1_a5_chain(monkeypatch) -> None:
    previous = _plan(plan_id=41)
    operational = _operational(last_action_plan_id=41)
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def none(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return operational

    async def latest_plan(*_args, **kwargs):
        assert kwargs["action_plan_id"] == 41
        return SimpleNamespace(id=41)

    async def current(*_args, **kwargs):
        assert kwargs["evaluated_at"] == NOW
        return {**deepcopy(previous), "action_plan_id": None}, {}

    async def chain(*_args, **_kwargs):
        return {}, {}, {}, {}

    async def must_not_freeze(*_args, **_kwargs):
        raise AssertionError("unchanged plan must not create A1-A5 snapshots")

    async def no_alert(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", none)
    monkeypatch.setattr(service, "_decision_by_fingerprint", none)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_latest_action_plan", latest_plan)
    monkeypatch.setattr(action_plan_service, "_decision_read", lambda _row: previous)
    monkeypatch.setattr(action_plan_service, "_chain_from_orchestration", chain)
    monkeypatch.setattr(
        action_plan_service, "current_action_plan_source_context", current
    )
    monkeypatch.setattr(action_plan_service, "create_action_plan_decision", must_not_freeze)
    monkeypatch.setattr(service, "deliver_continuous_alert", no_alert)

    result = await service.evaluate_continuous_autopilot(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="request-no-change",
        as_of=NOW,
    )
    assert result["status"] == "UNCHANGED"
    assert result["current_action_plan_id"] == 41
    assert operational.pending_categories == []
    assert operational.no_change_count == 1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_clean_manual_evaluation_is_a_bounded_status_check(monkeypatch) -> None:
    decision = _stored_decision()
    operational = _operational(
        status="UNCHANGED",
        pending_categories=[],
        last_continuous_decision_id=decision.id,
        last_action_plan_id=decision.current_action_plan_id,
    )
    session = _Session(get_value=decision)

    async def access(*_args, **_kwargs):
        return None

    calls = 0

    async def no_existing(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return operational

    async def must_not_evaluate(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("clean manual status check must not execute A1-A5")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(
        action_plan_service, "current_action_plan_source_context", must_not_evaluate
    )
    result = await service.evaluate_continuous_autopilot(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="manual-status-only",
    )
    assert result["continuous_decision_id"] == decision.id
    assert result["operational_status"] == "UNCHANGED"
    assert calls == 0
    assert session.commits == 1
    assert any(
        item.__class__.__name__ == "ContinuousAutopilotRequest"
        for item in session.added
    )


def test_manual_failure_cooldown_is_bounded_and_versioned() -> None:
    recent = _operational(status="FAILED", last_evaluated_at=NOW)
    assert service._manual_retry_after(
        recent, evaluated_at=NOW + timedelta(seconds=1)
    ) == 59
    assert service._manual_retry_after(
        recent, evaluated_at=NOW + timedelta(seconds=60)
    ) is None
    recent.status = "REEVALUATION_REQUIRED"
    assert service._manual_retry_after(recent, evaluated_at=NOW) is None


@pytest.mark.asyncio
async def test_recent_failed_manual_request_is_rejected_before_heavy_chain(
    monkeypatch,
) -> None:
    operational = _operational(status="FAILED", last_evaluated_at=NOW)
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def no_existing(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return operational

    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("cooldown must reject before evaluating A1-A5")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_now", lambda: NOW + timedelta(seconds=1))
    monkeypatch.setattr(
        action_plan_service, "current_action_plan_source_context", must_not_run
    )

    with pytest.raises(service.ContinuousAutopilotCooldownError) as captured:
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="fresh-key-during-failure",
        )
    assert captured.value.retry_after == 59
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_idempotency_key_rejects_different_request_fingerprint(monkeypatch) -> None:
    decision = _stored_decision()

    async def access(*_args, **_kwargs):
        return None

    async def existing(*_args, **_kwargs):
        return (
            decision,
            service._request_fingerprint(
                household_id=10, as_of=NOW, change_categories=()
            ),
        )

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    with pytest.raises(service.ContinuousAutopilotConflictError):
        await service.evaluate_continuous_autopilot(
            object(),
            household_id=10,
            user_id=91,
            idempotency_key="request-1",
            as_of=NOW.replace(hour=21),
        )


def test_operational_overlay_does_not_mutate_frozen_decision_contract() -> None:
    frozen = service._decision_read(_stored_decision())
    state = _operational(
        status="FAILED",
        pending_categories=["MARKET_DATA"],
        last_evaluated_at=NOW,
        last_successful_at=NOW.replace(hour=19),
    )
    current = service._with_operational_state(frozen, state)
    assert current["status"] == frozen["status"]
    assert current["decision_fingerprint"] == frozen["decision_fingerprint"]
    assert current["operational_status"] == "FAILED"
    assert current["pending_categories"] == ["MARKET_DATA"]
    assert current["last_evaluated_at"] == NOW
    assert current["operational_warnings"][0]["code"] == "LAST_EVALUATION_FAILED"


@pytest.mark.asyncio
async def test_current_uses_operational_pointer_not_latest_history(monkeypatch) -> None:
    pointed = _stored_decision()
    pointed.id = 50
    state = _operational(
        status="UNCHANGED",
        pending_categories=[],
        last_action_plan_id=pointed.current_action_plan_id,
        last_continuous_decision_id=50,
    )

    class PointerSession:
        async def get(self, model, key):
            if model is service.ContinuousAutopilotState:
                return state
            if model is service.ContinuousAutopilotDecision and key == 50:
                return pointed
            return None

    async def access(*_args, **_kwargs):
        return None

    async def must_not_use_latest(*_args, **_kwargs):
        raise AssertionError("state pointer is the current-decision authority")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_latest_decision", must_not_use_latest)
    result = await service.current_continuous_autopilot(
        PointerSession(), household_id=10, user_id=91
    )
    assert result["continuous_decision_id"] == 50
    assert result["current_action_plan_id"] == pointed.current_action_plan_id
    assert result["operational_status"] == "UNCHANGED"


@pytest.mark.asyncio
async def test_shared_member_projection_covers_current_evaluate_history_and_detail(
    monkeypatch,
) -> None:
    decision = _stored_decision(_mixed_private_payload())
    state = _operational(
        status="CHANGED",
        pending_categories=[],
        last_action_plan_id=decision.current_action_plan_id,
        last_continuous_decision_id=decision.id,
    )

    async def access(*_args, **_kwargs):
        return (
            SimpleNamespace(household_type="SHARED"),
            SimpleNamespace(user_id=91, status="ACTIVE"),
        )

    async def existing(*_args, **_kwargs):
        return (
            decision,
            service._request_fingerprint(
                household_id=10, as_of=None, change_categories=()
            ),
        )

    class CurrentSession:
        async def get(self, model, key):
            if model is service.ContinuousAutopilotState:
                return state
            if model is service.ContinuousAutopilotDecision and key == decision.id:
                return decision
            return None

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)

    current = await service.current_continuous_autopilot(
        CurrentSession(), household_id=10, user_id=91
    )
    evaluated = await service.evaluate_continuous_autopilot(
        _Session(get_value=state),
        household_id=10,
        user_id=91,
        idempotency_key="private-projection",
    )
    history = await service.continuous_autopilot_history(
        _Session(results=[_ScalarResult(1), _ScalarResult(values=[decision])]),
        household_id=10,
        user_id=91,
        limit=20,
        offset=0,
    )
    detail = await service.get_continuous_autopilot_decision(
        _Session(results=[_ScalarResult(decision)]),
        household_id=10,
        continuous_decision_id=decision.id,
        user_id=91,
    )

    for payload in (current, evaluated, detail):
        serialized = json.dumps(payload, default=str, sort_keys=True)
        assert "SEGREDO_92" not in serialized
        assert payload["materiality"] == "MEDIUM"
        assert len(payload["detected_changes"]) == 1
    assert history["items"][0]["materiality"] == "MEDIUM"
    assert history["items"][0]["change_count"] == 1


@pytest.mark.asyncio
async def test_prelock_technical_failure_is_mapped_to_unavailable(monkeypatch) -> None:
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def lookup_failure(*_args, **_kwargs):
        raise RuntimeError("database temporarily unavailable")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", lookup_failure)
    with pytest.raises(service.ContinuousAutopilotUnavailableError):
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="prelock-failure",
        )
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_prelock_domain_error_is_preserved(monkeypatch) -> None:
    session = _Session()

    async def denied(*_args, **_kwargs):
        raise state_service.HouseholdNotFoundError("not found")

    monkeypatch.setattr(state_service, "get_household_access", denied)
    with pytest.raises(state_service.HouseholdNotFoundError):
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="domain-error",
        )
    assert session.rollbacks == 0


def test_alert_episode_suppresses_active_condition_and_reopens_after_resolution() -> None:
    state = _operational()
    active = {
        "alert_decision": "IMPORTANT",
        "decision_fingerprint": "a" * 64,
        "alert": {"dedupe_key": "d" * 64},
    }
    resolved = {"alert_decision": "NO_ALERT", "alert": None}

    assert service._alert_episode_for_result(state, active) == 1
    assert service._alert_episode_for_result(state, active) == 1
    assert service._alert_episode_for_result(state, resolved) is None
    assert state.active_alert_key is None
    assert service._alert_episode_for_result(state, active) == 2


@pytest.mark.asyncio
async def test_material_change_freezes_chain_in_one_transaction(monkeypatch) -> None:
    previous = _plan(plan_id=41)
    live = deepcopy(previous)
    live["action_plan_id"] = None
    live["actions"][1]["action_type"] = "INVESTMENT_AVOID"
    live["actions"][1]["action_status"] = "AVOID"
    live["decision_fingerprint"] = "b" * 64
    frozen = deepcopy(live)
    frozen["action_plan_id"] = 42
    operational = _operational(pending_categories=["MARKET_DATA"])
    session = _Session()
    orchestration_calls = []
    action_calls = []

    async def access(*_args, **_kwargs):
        return None

    async def none(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return operational

    async def latest_plan(*_args, **_kwargs):
        return SimpleNamespace(id=41)

    async def current(*_args, **_kwargs):
        return live, {}

    async def chain(*_args, **_kwargs):
        return {}, {}, {}, {}

    async def freeze_orchestration(*_args, **kwargs):
        orchestration_calls.append(kwargs)
        return {"orchestration_id": 77}

    async def freeze_action(*_args, **kwargs):
        action_calls.append(kwargs)
        return frozen

    async def deliver(*_args, **_kwargs):
        return 2

    async def must_not_freeze_full_chain(*_args, **_kwargs):
        raise AssertionError("market-only changes must preserve frozen A1-A3")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", none)
    monkeypatch.setattr(service, "_decision_by_fingerprint", none)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_latest_action_plan", latest_plan)
    monkeypatch.setattr(action_plan_service, "_decision_read", lambda _row: previous)
    monkeypatch.setattr(action_plan_service, "_chain_from_orchestration", chain)
    monkeypatch.setattr(
        action_plan_service, "action_plan_from_allocation_source_context", current
    )
    monkeypatch.setattr(
        service.orchestration_service,
        "create_investment_orchestration_from_allocation_decision",
        freeze_orchestration,
    )
    monkeypatch.setattr(
        action_plan_service,
        "create_action_plan_from_orchestration_decision",
        freeze_action,
    )
    monkeypatch.setattr(
        action_plan_service,
        "create_action_plan_decision",
        must_not_freeze_full_chain,
    )
    monkeypatch.setattr(service, "deliver_continuous_alert", deliver)

    result = await service.evaluate_continuous_autopilot(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="request-change",
        as_of=NOW,
    )
    assert result["materiality"] == "CRITICAL"
    assert result["alert_decision"] == "CRITICAL"
    assert orchestration_calls[0]["commit"] is False
    assert orchestration_calls[0]["evaluated_at"] == NOW
    assert orchestration_calls[0]["allocation_id"] == previous[
        "capital_allocation_decision_id"
    ]
    assert action_calls[0]["commit"] is False
    assert action_calls[0]["orchestration_id"] == 77
    assert operational.last_action_plan_id == 42
    assert operational.alert_count == 2
    assert session.commits == 1


@pytest.mark.asyncio
async def test_mark_dirty_preserves_categories_without_commit() -> None:
    operational = _operational(status="UNCHANGED", pending_categories=["GOALS"])
    session = _Session([_ScalarResult(value=operational)])
    await service.mark_household_dirty(
        session, household_id=10, category="DEBT", dirty_at=NOW
    )
    assert operational.status == "REEVALUATION_REQUIRED"
    assert operational.pending_categories == ["DEBT", "GOALS"]
    assert session.commits == 0


@pytest.mark.asyncio
async def test_scheduler_query_excludes_archived_households() -> None:
    session = _Session([_ScalarResult(values=[])])
    assert await service.scheduled_households(session, limit=10) == []
    compiled = session.queries[0].compile()
    assert "JOIN households" in str(compiled)
    assert "households.status" in str(compiled)
    assert "ACTIVE" in compiled.params.values()


@pytest.mark.asyncio
async def test_failure_preserves_last_known_good_and_marks_operational_state(
    monkeypatch,
) -> None:
    previous = _plan(plan_id=41)
    operational = _operational(last_action_plan_id=41)
    failed = _operational(last_action_plan_id=41)
    session = _Session(get_value=operational)

    async def access(*_args, **_kwargs):
        return None

    async def none(*_args, **_kwargs):
        return None

    locks = iter([operational, failed])

    async def locked(*_args, **_kwargs):
        return next(locks)

    async def latest_plan(*_args, **_kwargs):
        return SimpleNamespace(id=41)

    async def chain(*_args, **_kwargs):
        return {}, {}, {}, {}

    async def provider_failure(*_args, **_kwargs):
        raise RuntimeError("market provider unavailable")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", none)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_latest_action_plan", latest_plan)
    monkeypatch.setattr(action_plan_service, "_decision_read", lambda _row: previous)
    monkeypatch.setattr(action_plan_service, "_chain_from_orchestration", chain)
    monkeypatch.setattr(
        action_plan_service,
        "current_action_plan_source_context",
        provider_failure,
    )

    with pytest.raises(
        service.ContinuousAutopilotUnavailableError,
        match="could not produce a safe decision",
    ):
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="request-failed",
            as_of=NOW,
        )
    assert failed.status == "FAILED"
    assert failed.last_action_plan_id == 41
    assert failed.failure_count == 1
    assert failed.last_error_code == "RuntimeError"
    assert session.rollbacks == 1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_failed_evaluation_cannot_overwrite_concurrent_success(monkeypatch) -> None:
    previous = _plan(plan_id=41)
    initial = _operational(
        last_action_plan_id=41,
        last_continuous_decision_id=50,
    )
    winner = _operational(
        status="CHANGED",
        pending_categories=[],
        last_action_plan_id=42,
        last_continuous_decision_id=51,
        last_successful_at=NOW,
    )
    session = _Session()
    locks = iter([initial, winner])

    async def access(*_args, **_kwargs):
        return None

    async def none(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return next(locks)

    async def latest_plan(*_args, **_kwargs):
        return SimpleNamespace(id=41)

    async def chain(*_args, **_kwargs):
        return {}, {}, {}, {}

    async def provider_failure(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", none)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_latest_action_plan", latest_plan)
    monkeypatch.setattr(action_plan_service, "_decision_read", lambda _row: previous)
    monkeypatch.setattr(action_plan_service, "_chain_from_orchestration", chain)
    monkeypatch.setattr(
        action_plan_service,
        "current_action_plan_source_context",
        provider_failure,
    )

    with pytest.raises(service.ContinuousAutopilotUnavailableError):
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="failed-while-winner-commits",
            as_of=NOW,
        )
    assert winner.status == "CHANGED"
    assert winner.failure_count == 0
    assert session.commits == 0
    assert session.rollbacks == 2


@pytest.mark.asyncio
async def test_failed_evaluation_preserves_deduplicated_concurrent_success(
    monkeypatch,
) -> None:
    previous = _plan(plan_id=41)
    initial = _operational(
        last_action_plan_id=41,
        last_continuous_decision_id=50,
        last_successful_at=NOW.replace(hour=20),
        evaluation_count=4,
    )
    winner = _operational(
        status="UNCHANGED",
        pending_categories=[],
        last_action_plan_id=41,
        # A fingerprint-deduplicated winner legitimately keeps the same id.
        last_continuous_decision_id=50,
        last_successful_at=NOW,
        evaluation_count=5,
    )
    session = _Session()
    locks = iter([initial, winner])

    async def access(*_args, **_kwargs):
        return None

    async def none(*_args, **_kwargs):
        return None

    async def locked(*_args, **_kwargs):
        return next(locks)

    async def latest_plan(*_args, **_kwargs):
        return SimpleNamespace(id=41)

    async def chain(*_args, **_kwargs):
        return {}, {}, {}, {}

    async def provider_failure(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", none)
    monkeypatch.setattr(service, "_state_for_update", locked)
    monkeypatch.setattr(service, "_latest_action_plan", latest_plan)
    monkeypatch.setattr(action_plan_service, "_decision_read", lambda _row: previous)
    monkeypatch.setattr(action_plan_service, "_chain_from_orchestration", chain)
    monkeypatch.setattr(
        action_plan_service,
        "current_action_plan_source_context",
        provider_failure,
    )

    with pytest.raises(service.ContinuousAutopilotUnavailableError):
        await service.evaluate_continuous_autopilot(
            session,
            household_id=10,
            user_id=91,
            idempotency_key="failed-while-deduplicated-winner-commits",
            as_of=NOW,
        )
    assert winner.status == "UNCHANGED"
    assert winner.failure_count == 0
    assert winner.last_continuous_decision_id == 50
    assert session.commits == 0
    assert session.rollbacks == 2
