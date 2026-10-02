from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest

from backend.app.continuous_autopilot.engine import calculate_continuous_autopilot
from backend.app.continuous_autopilot.rules import (
    ENGINE_VERSION,
    MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD,
    RULESET,
    RULESET_FINGERPRINT,
    RULES_VERSION,
    reevaluation_scope,
)
from backend.app.continuous_autopilot.schemas import ContinuousAutopilotRead


NOW = datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc)


def _action(
    action_id: str,
    action_type: str,
    *,
    rank: int,
    amount: str | None,
    owner: int | None = None,
) -> dict:
    return {
        "action_id": action_id,
        "category": "INVESTMENT" if action_type.startswith("INVESTMENT") else "FINANCIAL",
        "action_type": action_type,
        "priority_rank": rank,
        "title": action_type,
        "description": "Descrição factual",
        "ownership_scope": "PERSONAL" if owner else "HOUSEHOLD",
        "owner_user_id": owner,
        "household_id": 10,
        "currency": "BRL",
        "amount": amount,
        "target_amount": None,
        "remaining_need": None,
        "liability_id": None,
        "goal_id": None,
        "asset_id": 100 if action_type.startswith("INVESTMENT") else None,
        "symbol": "TEST3" if action_type.startswith("INVESTMENT") else None,
        "asset_class": "ACOES" if action_type.startswith("INVESTMENT") else None,
        "quantity_candidate": 1 if action_type == "INVESTMENT_BUY" else None,
        "price_reference": "100.00" if action_type.startswith("INVESTMENT") else None,
        "price_timestamp": NOW,
        "price_source": "TEST",
        "freshness_status": "FRESH",
        "action_status": {
            "INVESTMENT_BUY": "ACTIONABLE",
            "INVESTMENT_WAIT": "WAIT",
            "INVESTMENT_AVOID": "AVOID",
        }.get(action_type, "ACTIONABLE"),
        "severity": "INFO",
        "reason": "Decisão herdada de A5",
        "evidence": [],
        "warnings": [],
        "blockers": [],
        "missing_information": [],
        "source_engine": "action-plan-v1",
        "source_decision_id": 31,
        "source_reference": {},
        "generated_at": NOW,
    }


def _plan(*, plan_id: int | None, status: str = "READY") -> dict:
    actions = [
        _action("reserve", "EMERGENCY_RESERVE_CONTRIBUTION", rank=1, amount="600.00"),
        _action("buy-test3", "INVESTMENT_BUY", rank=2, amount="100.00", owner=91),
        _action("hold", "HOLD_CASH", rank=3, amount="50.00"),
    ]
    return {
        "action_plan_id": plan_id,
        "household_id": 10,
        "financial_state_snapshot_id": 7,
        "financial_policy_decision_id": 17,
        "capital_allocation_decision_id": 23,
        "investment_orchestration_decision_id": 31,
        "engine_version": "action-plan-v1",
        "rules_version": "action-plan-rules-v1",
        "status": status,
        "currency": "BRL",
        "period": "MONTHLY",
        "summary": {
            "authorized_financial_capital": "750.00",
            "authorized_investment_capital": "150.00",
            "financial_actions_total": "600.00",
            "investment_buy_total": "100.00",
            "hold_cash_total": "50.00",
            "action_count": 3,
            "primary_action": "Fortalecer reserva",
        },
        "actions": actions,
        "information_actions": [],
        "financial_actions": [actions[0]],
        "investment_actions": [actions[1]],
        "hold_actions": [actions[2]],
        "total_financial_actions": "600.00",
        "total_investment_actions": "100.00",
        "total_hold_cash": "50.00",
        "speculative_capital": "0.00",
        "trading_dispatch": False,
        "blockers": [],
        "warnings": [],
        "missing_information": [],
        "evidence": [],
        "rule_traces": [],
        "state_fingerprint": "1" * 64,
        "policy_fingerprint": "2" * 64,
        "allocation_fingerprint": "3" * 64,
        "orchestration_fingerprint": "4" * 64,
        "ruleset_fingerprint": "5" * 64,
        "decision_fingerprint": "a" * 64,
        "generated_at": NOW,
        "created_at": NOW if plan_id else None,
    }


def _evaluate(previous: dict | None, current: dict, **kwargs) -> dict:
    return calculate_continuous_autopilot(
        previous,
        current,
        as_of=NOW,
        observed_at=NOW,
        change_categories=kwargs.pop("change_categories", ["FINANCIAL_DATA"]),
        **kwargs,
    )


def test_initial_plan_is_a_no_alert_baseline() -> None:
    result = _evaluate(None, _plan(plan_id=42))
    assert result["engine_version"] == ENGINE_VERSION
    assert result["rules_version"] == RULES_VERSION
    assert result["status"] == "UP_TO_DATE"
    assert result["materiality"] == "NONE"
    assert result["alert_decision"] == "NO_ALERT"
    assert result["plan_diff"]["summary"].startswith("O primeiro")
    ContinuousAutopilotRead.model_validate(result)


def test_same_frozen_inputs_are_deterministic_and_unchanged() -> None:
    previous = _plan(plan_id=41)
    current = deepcopy(previous)
    current["action_plan_id"] = 42
    first = _evaluate(previous, current)
    second = _evaluate(previous, current)
    assert first == second
    assert first["status"] == "UNCHANGED"
    assert first["materiality"] == "NONE"
    assert first["detected_changes"] == []
    assert first["decision_fingerprint"] == second["decision_fingerprint"]


def test_fingerprint_only_change_is_low_informational_and_not_actionable() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current, change_categories=["FRESHNESS"])
    assert result["materiality"] == "LOW"
    assert result["alert_decision"] == "INFORMATIONAL"
    assert result["detected_changes"][0]["change_type"] == (
        "PLAN_FINGERPRINT_CHANGED"
    )


@pytest.mark.parametrize(
    ("before_type", "after_type", "materiality", "alert"),
    [
        ("INVESTMENT_BUY", "INVESTMENT_WAIT", "HIGH", "IMPORTANT"),
        ("INVESTMENT_BUY", "INVESTMENT_AVOID", "CRITICAL", "CRITICAL"),
        ("INVESTMENT_WAIT", "INVESTMENT_BUY", "HIGH", "IMPORTANT"),
    ],
)
def test_investment_transitions_are_structured_and_material(
    before_type: str, after_type: str, materiality: str, alert: str
) -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    previous["actions"][1] = _action("opportunity", before_type, rank=2, amount="100.00")
    current["actions"][1] = _action("opportunity", after_type, rank=2, amount="100.00")
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current, change_categories=["MARKET_DATA"])
    assert result["reevaluation_scope"] == "INVESTMENT_CHAIN"
    assert result["materiality"] == materiality
    assert result["alert_decision"] == alert
    assert result["plan_diff"]["changed_actions"][0]["transition"] == {
        "previous": before_type.removeprefix("INVESTMENT_"),
        "current": after_type.removeprefix("INVESTMENT_"),
    }


def test_added_removed_amount_and_rank_changes_are_not_text_diffs() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["actions"] = [
        {**current["actions"][0], "amount": "500.00", "priority_rank": 2},
        current["actions"][2],
        _action("goal", "GOAL_CONTRIBUTION", rank=1, amount="200.00"),
    ]
    current["total_financial_actions"] = "700.00"
    current["total_investment_actions"] = "0.00"
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current, change_categories=["GOALS"])
    diff = result["plan_diff"]
    assert [item["action_id"] for item in diff["added_actions"]] == ["goal"]
    assert [item["action_id"] for item in diff["removed_actions"]] == ["buy-test3"]
    assert diff["changed_actions"][0]["changed_fields"] == ["amount", "priority_rank"]
    assert diff["financial_delta"] == 100
    assert diff["investment_delta"] == -100
    assert diff["priority_changes"][0]["current"] == 2


def test_real_zero_and_missing_amount_are_distinct() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    previous["actions"][0]["amount"] = None
    current["actions"][0]["amount"] = "0.00"
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current)
    change = result["plan_diff"]["changed_actions"][0]
    assert change["before"]["amount"] is None
    assert change["after"]["amount"] == "0.00"
    assert change["amount_delta"] is None
    assert result["detected_changes"][0]["delta"] is None
    assert result["materiality"] == "MEDIUM"


def test_insignificant_monetary_change_is_audited_without_action_alert() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["actions"][0]["amount"] = "600.01"
    current["total_financial_actions"] = "600.01"
    current["decision_fingerprint"] = "b" * 64

    result = _evaluate(previous, current)

    assert result["materiality"] == "LOW"
    assert result["alert_decision"] == "INFORMATIONAL"
    assert str(result["detected_changes"][0]["delta"]) == "0.01"


@pytest.mark.parametrize(
    ("before", "after", "materiality"),
    [
        ("150.00", "150.01", "LOW"),
        ("150.00", "151.00", "MEDIUM"),
        (None, "0.00", "MEDIUM"),
    ],
)
def test_investment_bucket_uses_versioned_absolute_threshold(
    before: str | None, after: str, materiality: str
) -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(
        previous,
        current,
        previous_context={"allocation": {"investment_bucket_amount": before}},
        current_context={"allocation": {"investment_bucket_amount": after}},
    )
    bucket_change = next(
        item
        for item in result["detected_changes"]
        if item["change_type"] == "INVESTMENT_BUCKET_CHANGED"
    )
    assert bucket_change["materiality"] == materiality
    assert result["materiality"] == materiality


def test_ruleset_fingerprint_freezes_all_materiality_inputs() -> None:
    assert MONETARY_ABSOLUTE_MATERIALITY_THRESHOLD == 1
    for key in (
        "monetary_absolute_materiality_threshold",
        "action_material_fields",
        "plan_status_materiality",
        "data_quality_materiality",
        "allocation_status_materiality",
        "orchestration_status_materiality",
        "fingerprint_only_materiality",
        "manual_failed_retry_cooldown_seconds",
    ):
        assert key in RULESET
    assert len(RULESET_FINGERPRINT) == 64


def test_missing_totals_are_not_coerced_to_zero_in_plan_delta() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    previous["total_financial_actions"] = None
    current["total_financial_actions"] = "0.00"
    previous["total_investment_actions"] = "invalid"
    current["total_investment_actions"] = "0.00"
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current)
    assert result["plan_diff"]["financial_delta"] is None
    assert result["plan_diff"]["investment_delta"] is None


def test_profile_and_freshness_require_full_financial_chain() -> None:
    assert reevaluation_scope(["PROFILE"]) == "FULL_CHAIN"
    assert reevaluation_scope(["FRESHNESS"]) == "FULL_CHAIN"
    assert reevaluation_scope(["MARKET_DATA"]) == "INVESTMENT_CHAIN"


def test_readiness_downgrade_is_critical_when_context_is_available() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(
        previous,
        current,
        previous_context={"policy": {"investment_readiness": "READY"}},
        current_context={"policy": {"investment_readiness": "BLOCKED"}},
    )
    assert result["materiality"] == "CRITICAL"
    assert any(
        item["change_type"] == "INVESTMENT_READINESS_CHANGED"
        for item in result["detected_changes"]
    )


def test_frozen_chain_context_changes_are_structured_not_recalculated() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(
        previous,
        current,
        previous_context={
            "state": {"data_quality": "COMPLETE"},
            "policy": {
                "policy_state": "BALANCED_BUILD",
                "investment_readiness": "LIMITED",
            },
            "allocation": {
                "allocation_status": "ACTIVE",
                "investment_bucket_amount": "150.00",
            },
            "orchestration": {"status": "ACTIVE"},
        },
        current_context={
            "state": {"data_quality": "STALE"},
            "policy": {
                "policy_state": "DEBT_PRIORITY",
                "investment_readiness": "LIMITED",
            },
            "allocation": {
                "allocation_status": "CONSTRAINED",
                "investment_bucket_amount": "0.00",
            },
            "orchestration": {"status": "NO_SUITABLE_OPPORTUNITY"},
        },
    )
    change_types = {item["change_type"] for item in result["detected_changes"]}
    assert {
        "DATA_QUALITY_CHANGED",
        "POLICY_STATE_CHANGED",
        "ALLOCATION_STATUS_CHANGED",
        "INVESTMENT_BUCKET_CHANGED",
        "ORCHESTRATION_STATUS_CHANGED",
    }.issubset(change_types)
    assert result["materiality"] == "HIGH"


def test_plan_status_blocked_is_critical_and_keeps_reason() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42, status="BLOCKED")
    current["decision_fingerprint"] = "b" * 64
    result = _evaluate(previous, current, change_categories=["DATA_QUALITY"])
    assert result["status"] == "CHANGED"
    assert result["materiality"] == "CRITICAL"
    assert result["alert"]["recommended_action"]


def test_household_mismatch_is_rejected_before_diff() -> None:
    previous = _plan(plan_id=41)
    current = _plan(plan_id=42)
    current["household_id"] = 11
    with pytest.raises(ValueError, match="different households"):
        _evaluate(previous, current)


def test_unknown_category_does_not_create_a_parallel_dependency_rule() -> None:
    result = _evaluate(
        _plan(plan_id=41),
        _plan(plan_id=42),
        change_categories=["UNKNOWN"],
    )
    assert result["change_categories"] == []
    assert result["reevaluation_scope"] == "NONE"
