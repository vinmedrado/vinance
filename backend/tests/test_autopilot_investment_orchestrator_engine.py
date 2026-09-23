from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.capital_allocation.engine import (
    calculate_capital_allocation,
    decision_fingerprint_from_payload as allocation_fingerprint,
)
from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_state.engine import calculate_financial_state
from backend.app.investment_orchestrator.engine import (
    calculate_investment_orchestration,
)
from backend.app.investment_orchestrator.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.investment_orchestrator.schemas import InvestmentOrchestrationRead
from backend.tests.test_autopilot_financial_policy_engine import _complete_inputs


NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _chain():
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    policy = calculate_financial_policy(state, normalized_inputs=inputs)
    allocation = calculate_capital_allocation(state, policy)
    return state, policy, allocation


def _profile(value: str = "MODERATE", status: str = "COMPLETE"):
    return {
        "status": status,
        "effective_profile": value,
        "investment_horizon": "LONG_TERM",
        "members": [{"user_id": 1, "profile": value}],
        "missing_member_user_ids": [],
        "inconsistent_member_user_ids": [],
    }


def _portfolio(status: str = "COMPLETE", concentration=None):
    return {
        "status": status,
        "positions": [],
        "concentration": concentration or [],
        "missing_information": [] if status == "COMPLETE" else ["owned_assets"],
    }


def _candidate(
    ticker: str = "TEST3",
    market: str = "ACOES",
    score: str | None = "80",
    price: str | None = "100",
    guardrail: str = "APPROVED",
    risk: str = "LOW",
    freshness: str = "FRESH",
):
    return {
        "asset_id": 1,
        "symbol": ticker,
        "ticker": ticker,
        "asset_class": market,
        "market": market,
        "price_reference": Decimal(price) if price is not None else None,
        "quantity_candidate": 100,
        "capital_required": Decimal("5000"),
        "recommendation_score": Decimal(score) if score is not None else None,
        "score_total": Decimal(score) if score is not None else None,
        "liquidity_score": Decimal("90"),
        "risk_level": risk,
        "guardrail_status": guardrail,
        "reasons": ["evidence"],
        "warnings": [],
        "freshness_status": freshness,
        "data_timestamp": NOW,
        "score_source": "vinance_score_v1",
        "guardrail_source": "vinance_guardrail_v1",
        "price_source": "vinance_score_v1",
    }


def _market(*candidates, failures=None, status: str = "AVAILABLE"):
    markets = []
    for market in sorted({item["market"] for item in candidates}):
        markets.append(
            {
                "market": market,
                "status": "AVAILABLE",
                "freshness_status": candidates[0].get("freshness_status", "FRESH"),
            }
        )
    return {
        "captured_at": NOW,
        "status": status,
        "markets": markets,
        "candidates": list(candidates),
        "partial_failures": failures or [],
        "missing_information": [],
        "sources": {},
    }


def _run(*, profile=None, portfolio=None, market=None, allocation=None, generated_at=NOW):
    state, policy, canonical_allocation = _chain()
    return calculate_investment_orchestration(
        state,
        policy,
        allocation or canonical_allocation,
        profile_context=profile or _profile(),
        portfolio_context=portfolio or _portfolio(),
        market_context=market or _market(_candidate()),
        generated_at=generated_at,
    )


def test_active_strategy_is_versioned_explainable_and_conservative() -> None:
    result = _run()
    assert result["engine_version"] == ENGINE_VERSION
    assert result["rules_version"] == RULES_VERSION
    assert result["status"] == "ACTIVE"
    assert result["suggested_capital"] <= result["investment_budget"]
    assert result["suggested_capital"] + result["remaining_investment_cash"] == result["investment_budget"]
    assert result["speculative_capital"] == 0
    assert result["trading_dispatch"] is False
    assert result["ranked_opportunities"][0]["action"] == "BUY"
    InvestmentOrchestrationRead.model_validate(result)


def test_same_frozen_inputs_have_same_decision_fingerprint() -> None:
    first = _run(generated_at=NOW)
    second = _run(generated_at=NOW + timedelta(hours=1))
    assert first["decision_fingerprint"] == second["decision_fingerprint"]
    assert first["class_allocations"] == second["class_allocations"]


def test_zero_investment_bucket_blocks_without_inventing_capital() -> None:
    _, _, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["investment_bucket_amount"] = Decimal("0.00")
    allocation["allocated_capital"] = Decimal("0.00")
    allocation["remaining_capital"] = allocation["allocatable_capital"]
    allocation["bucket_totals"]["investment_capital"] = Decimal("0.00")
    allocation["allocations"] = []
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    result = _run(allocation=allocation)
    assert result["status"] == "BLOCKED"
    assert result["suggested_capital"] == 0


@pytest.mark.parametrize("status", ["MISSING", "INCONSISTENT"])
def test_missing_or_inconsistent_profile_never_defaults_to_moderate(status: str) -> None:
    profile = _profile(status=status)
    profile["effective_profile"] = None
    result = _run(profile=profile)
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "INVESTOR_PROFILE_REQUIRED" for item in result["blockers"])


@pytest.mark.parametrize(
    ("guardrail", "expected"),
    [("WARNING", "WAIT"), ("BLOCKED", "AVOID"), ("UNKNOWN", "NO_RECOMMENDATION")],
)
def test_guardrails_prevail_over_score_and_budget(guardrail: str, expected: str) -> None:
    result = _run(market=_market(_candidate(guardrail=guardrail)))
    assert result["status"] == "NO_SUITABLE_OPPORTUNITY"
    assert result["ranked_opportunities"][0]["action"] == expected
    assert result["suggested_capital"] == 0


@pytest.mark.parametrize(
    "candidate",
    [_candidate(freshness="STALE"), _candidate(price=None), _candidate(score=None)],
)
def test_stale_price_missing_or_score_missing_never_buys(candidate) -> None:
    result = _run(market=_market(candidate))
    assert result["ranked_opportunities"][0]["action"] != "BUY"
    assert result["suggested_capital"] == 0


def test_missing_liquidity_score_never_becomes_implicit_high_liquidity() -> None:
    candidate = _candidate()
    candidate["liquidity_score"] = None
    result = _run(market=_market(candidate))
    assert result["ranked_opportunities"][0]["action"] == "WAIT"
    assert result["suggested_capital"] == 0


def test_unknown_investment_horizon_limits_and_remains_explicit() -> None:
    profile = _profile()
    profile["investment_horizon"] = None
    result = _run(profile=profile)
    assert result["status"] == "LIMITED"
    assert any(item["code"] == "INVESTMENT_HORIZON_UNKNOWN" for item in result["warnings"])
    assert any(item["code"] == "INVESTMENT_HORIZON_REQUIRED" for item in result["missing_information"])


def test_financial_data_quality_gate_fails_closed() -> None:
    state, policy, allocation = _chain()
    state = deepcopy(state)
    state["data_quality"] = "INCONSISTENT"
    result = calculate_investment_orchestration(
        state,
        policy,
        allocation,
        profile_context=_profile(),
        portfolio_context=_portfolio(),
        market_context=_market(_candidate()),
        generated_at=NOW,
    )
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "FINANCIAL_DATA_GATE_BLOCKED" for item in result["blockers"])


def test_every_versioned_rule_is_present_in_audit_trace() -> None:
    result = _run()
    trace_ids = {item["rule_id"] for item in result["rule_traces"]}
    from backend.app.investment_orchestrator.rules import RULE_CATALOG

    assert trace_ids == set(RULE_CATALOG)


def test_unknown_portfolio_limits_but_does_not_assume_zero_positions() -> None:
    result = _run(portfolio=_portfolio(status="UNKNOWN"))
    assert result["status"] == "LIMITED"
    assert any(item["code"] == "PORTFOLIO_UNKNOWN" for item in result["warnings"])
    assert result["portfolio_context"]["status"] == "UNKNOWN"


def test_known_concentration_makes_same_market_ineligible() -> None:
    result = _run(
        portfolio=_portfolio(
            concentration=[{"market": "ACOES", "percentage": Decimal("75")}]
        )
    )
    assert result["status"] == "NO_SUITABLE_OPPORTUNITY"
    decision = next(item for item in result["asset_class_decisions"] if item["market"] == "ACOES")
    assert decision["eligibility"] == "INELIGIBLE"


def test_dynamic_class_distribution_uses_relative_scores_not_fixed_weights() -> None:
    result = _run(
        market=_market(
            _candidate("AAA3", "ACOES", score="80", price="10"),
            _candidate("ETF1", "ETF", score="40", price="10"),
        )
    )
    amounts = {row["market"]: row["allocated_amount"] for row in result["class_allocations"]}
    assert amounts["ACOES"] > amounts["ETF"]
    assert sum(amounts.values()) == result["investment_budget"]
    assert amounts["ACOES"] != result["investment_budget"] * Decimal("0.30")


def test_opportunities_are_ranked_globally_by_safe_action_and_score() -> None:
    result = _run(
        market=_market(
            _candidate("LOW3", "ACOES", score="40", price="10"),
            _candidate("TOP11", "ETF", score="90", price="10"),
        )
    )

    assert [item["rank"] for item in result["ranked_opportunities"]] == [1, 2]
    assert result["ranked_opportunities"][0]["ticker"] == "TOP11"


def test_only_one_budget_advisor_alternative_per_class_commits_capital() -> None:
    result = _run(
        market=_market(
            _candidate("AAA3", score="90", price="100"),
            _candidate("BBB3", score="80", price="100"),
        )
    )
    buys = [item for item in result["ranked_opportunities"] if item["action"] == "BUY"]
    assert len(buys) == 1
    assert sum(item["capital_committed"] for item in result["ranked_opportunities"]) <= result["investment_budget"]


def test_conservative_profile_rejects_known_high_risk() -> None:
    result = _run(
        profile=_profile("CONSERVATIVE"),
        market=_market(_candidate(risk="HIGH")),
    )
    assert result["ranked_opportunities"][0]["action"] == "AVOID"
    assert result["suggested_capital"] == 0


def test_mixed_household_profile_uses_explicit_conservative_context() -> None:
    profile = _profile("CONSERVATIVE", "MIXED")
    profile["members"].append({"user_id": 2, "profile": "AGGRESSIVE"})
    result = _run(profile=profile)
    assert result["status"] == "LIMITED"
    assert result["profile_context"]["effective_profile"] == "CONSERVATIVE"


def test_partial_provider_failure_isolated_when_another_class_is_safe() -> None:
    result = _run(
        market=_market(_candidate(), failures=[{"market": "ETF", "error": "Timeout"}])
    )
    assert result["status"] == "LIMITED"
    assert result["suggested_capital"] > 0
    assert any(item["code"] == "MARKET_CLASS_UNAVAILABLE" for item in result["warnings"])


def test_all_market_context_failure_blocks() -> None:
    result = _run(market=_market(status="UNAVAILABLE"))
    assert result["status"] == "BLOCKED"
    assert result["remaining_investment_cash"] == result["investment_budget"]


def test_fixed_income_and_crypto_are_not_falsely_declared_supported() -> None:
    result = _run()
    decisions = {item["asset_class"]: item for item in result["asset_class_decisions"]}
    assert decisions["FIXED_INCOME"]["eligibility"] == "UNKNOWN"
    assert decisions["CRYPTO"]["eligibility"] == "UNKNOWN"


def test_allocation_fingerprint_tampering_fails_closed() -> None:
    _, _, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["investment_bucket_amount"] = Decimal("999")
    result = _run(allocation=allocation)
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "ALLOCATION_FINGERPRINT_INVALID" for item in result["blockers"])


def test_financial_state_must_match_allocation_input_fingerprint() -> None:
    state, policy, allocation = _chain()
    state = deepcopy(state)
    state["metrics"]["net_worth"] = Decimal("999999.99")

    result = calculate_investment_orchestration(
        state,
        policy,
        allocation,
        profile_context=_profile(),
        portfolio_context=_portfolio(),
        market_context=_market(_candidate()),
        generated_at=NOW,
    )

    assert result["status"] == "BLOCKED"
    assert any(
        item["code"] == "STATE_ALLOCATION_INPUT_MISMATCH"
        for item in result["blockers"]
    )


def test_unknown_allocation_status_fails_closed_even_with_valid_fingerprint() -> None:
    _, _, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["allocation_status"] = "UNRECOGNIZED"
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)

    result = _run(allocation=allocation)

    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "ALLOCATION_STATUS_INVALID" for item in result["blockers"])
