from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.financial.budget_engine import calculate_budget_strategy
from backend.app.intelligence import service as intelligence_service
from backend.app.intelligence.allocation import calculate_allocation
from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.investor_profile_service import AGGRESSIVE, CONSERVATIVE, MODERATE
from backend.app.intelligence.services.recommendation_guardrail_service import APPROVED, BLOCKED, WARNING


def _score(ticker: str, score_total: str, *, price: str = "50") -> SimpleNamespace:
    return SimpleNamespace(
        ticker=ticker,
        market="FII",
        date=date(2026, 8, 25),
        score_total=Decimal(score_total),
        price=Decimal(price),
    )


def _guardrail(ticker: str, status: str, risk_level: str) -> SimpleNamespace:
    return SimpleNamespace(
        ticker=ticker,
        status=status,
        risk_level=risk_level,
        reasons_json={"blocked": [], "warnings": [status] if status == WARNING else [], "summary": [status]},
    )


def _guardrails(*rows: tuple[str, str, str]) -> dict[str, SimpleNamespace]:
    return {ticker: _guardrail(ticker, status, risk_level) for ticker, status, risk_level in rows}


def _fixed_income_percentage(result: dict) -> Decimal:
    return next(item["percentage"] for item in result["allocation"] if item["asset_class"] == "renda_fixa")


@pytest.mark.parametrize(
    ("scores", "guardrails", "expected"),
    [
        (
            [_score("AAA11", "80"), _score("BBB11", "90")],
            _guardrails(("AAA11", APPROVED, "LOW"), ("BBB11", APPROVED, "LOW")),
            ["BBB11", "AAA11"],
        ),
        (
            [_score("AAA11", "95"), _score("BBB11", "90")],
            _guardrails(("AAA11", WARNING, "MEDIUM"), ("BBB11", APPROVED, "LOW")),
            ["BBB11", "AAA11"],
        ),
        (
            [_score("AAA11", "80"), _score("BBB11", "90")],
            _guardrails(("AAA11", WARNING, "MEDIUM"), ("BBB11", WARNING, "MEDIUM")),
            ["BBB11", "AAA11"],
        ),
        (
            [_score("AAA11", "80"), _score("BBB11", "100")],
            _guardrails(("AAA11", WARNING, "MEDIUM"), ("BBB11", BLOCKED, "HIGH")),
            ["AAA11"],
        ),
        (
            [_score("AAA11", "80"), _score("BBB11", "100")],
            _guardrails(("AAA11", APPROVED, "LOW"), ("BBB11", BLOCKED, "HIGH")),
            ["AAA11"],
        ),
    ],
    ids=[
        "approved-approved",
        "approved-warning",
        "warning-warning",
        "warning-blocked",
        "approved-blocked",
    ],
)
def test_guardrail_pair_matrix_respects_eligibility_and_final_score(scores, guardrails, expected) -> None:
    items = build_budget_items(
        scores,
        budget=Decimal("150"),
        limit=20,
        guardrails=guardrails,
        include_warnings=True,
        profile=MODERATE,
    )

    assert [item.ticker for item in items] == expected
    assert all(item.status != BLOCKED for item in items)


def test_equal_recommendation_scores_use_ticker_as_stable_tiebreaker() -> None:
    items = build_budget_items(
        [_score("ZZZ11", "90"), _score("AAA11", "90")],
        budget=Decimal("150"),
        limit=20,
        guardrails=_guardrails(("ZZZ11", APPROVED, "LOW"), ("AAA11", APPROVED, "LOW")),
    )

    assert [item.ticker for item in items] == ["AAA11", "ZZZ11"]
    assert items[0].recommendation_score == items[1].recommendation_score


def test_higher_raw_score_does_not_bypass_guardrail_when_final_score_is_lower() -> None:
    items = build_budget_items(
        [_score("WARN11", "95"), _score("SAFE11", "90")],
        budget=Decimal("150"),
        limit=1,
        guardrails=_guardrails(("WARN11", WARNING, "MEDIUM"), ("SAFE11", APPROVED, "LOW")),
        include_warnings=True,
        profile=MODERATE,
    )

    assert [item.ticker for item in items] == ["SAFE11"]


def test_warning_can_lead_only_when_its_final_recommendation_score_is_higher() -> None:
    items = build_budget_items(
        [_score("WARN11", "100"), _score("SAFE11", "80")],
        budget=Decimal("150"),
        limit=20,
        guardrails=_guardrails(("WARN11", WARNING, "MEDIUM"), ("SAFE11", APPROVED, "LOW")),
        include_warnings=True,
        profile=MODERATE,
    )

    assert [item.ticker for item in items] == ["WARN11", "SAFE11"]
    assert items[0].recommendation_score > items[1].recommendation_score


def test_absence_of_approved_candidate_requires_warning_opt_in() -> None:
    scores = [_score("WARN11", "90")]
    guardrails = _guardrails(("WARN11", WARNING, "MEDIUM"))

    assert build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails) == []
    included = build_budget_items(
        scores,
        budget=Decimal("150"),
        limit=20,
        guardrails=guardrails,
        include_warnings=True,
        profile=MODERATE,
    )
    assert [item.ticker for item in included] == ["WARN11"]


@pytest.mark.parametrize(
    ("profile", "risk_level", "expected"),
    [
        (CONSERVATIVE, "MEDIUM", []),
        (MODERATE, "MEDIUM", ["WARN11"]),
        (AGGRESSIVE, "HIGH", ["WARN11"]),
    ],
)
def test_warning_eligibility_still_depends_on_investor_profile(profile, risk_level, expected) -> None:
    items = build_budget_items(
        [_score("WARN11", "90")],
        budget=Decimal("150"),
        limit=20,
        guardrails=_guardrails(("WARN11", WARNING, risk_level)),
        include_warnings=True,
        profile=profile,
    )

    assert [item.ticker for item in items] == expected


def test_budget_and_quantity_are_unchanged_by_guardrail_ranking() -> None:
    items = build_budget_items(
        [_score("SAFE11", "90", price="40"), _score("EXPENSIVE11", "100", price="151")],
        budget=Decimal("150"),
        limit=20,
        guardrails=_guardrails(("SAFE11", APPROVED, "LOW"), ("EXPENSIVE11", APPROVED, "LOW")),
    )

    assert [item.ticker for item in items] == ["SAFE11"]
    assert items[0].quantity_possible == 3
    assert items[0].invested_amount == Decimal("120.00")
    assert Decimal("150.00") - items[0].invested_amount == Decimal("30.00")


def test_omitted_reserve_months_does_not_invent_a_zero_reserve() -> None:
    normal = calculate_allocation(
        investment_capacity=Decimal("1000"),
        risk_profile="moderate",
        financial_score=80,
        emergency_reserve_priority=False,
    )
    adjusted = calculate_allocation(
        investment_capacity=Decimal("1000"),
        risk_profile="moderate",
        financial_score=80,
        emergency_reserve_priority=True,
    )

    assert _fixed_income_percentage(normal) == Decimal("25.00")
    assert _fixed_income_percentage(adjusted) == Decimal("43.00")
    assert not normal["warnings"]
    assert any("Reserva de emergência" in warning for warning in adjusted["warnings"])


@pytest.mark.parametrize(
    ("reserve_months", "expected_fixed_income"),
    [
        (Decimal("2.99"), Decimal("43.00")),
        (Decimal("3.00"), Decimal("25.00")),
        (Decimal("3.01"), Decimal("25.00")),
    ],
    ids=["below-target", "at-target", "above-target"],
)
def test_emergency_reserve_threshold_is_strictly_below_three_months(reserve_months, expected_fixed_income) -> None:
    result = calculate_allocation(
        investment_capacity=Decimal("1000"),
        risk_profile="moderate",
        financial_score=80,
        emergency_reserve_priority=False,
        emergency_reserve_months=reserve_months,
    )

    assert _fixed_income_percentage(result) == expected_fixed_income


def test_explicit_reserve_priority_still_applies_at_or_above_target() -> None:
    result = calculate_allocation(
        investment_capacity=Decimal("1000"),
        risk_profile="moderate",
        financial_score=80,
        emergency_reserve_priority=True,
        emergency_reserve_months=Decimal("6"),
    )

    assert _fixed_income_percentage(result) == Decimal("43.00")


@pytest.mark.parametrize(
    ("profile", "base_fixed_income", "priority_fixed_income"),
    [
        ("conservative", Decimal("40.00"), Decimal("48.50")),
        ("moderate", Decimal("25.00"), Decimal("43.00")),
        ("aggressive", Decimal("10.00"), Decimal("37.50")),
    ],
)
def test_reserve_priority_preserves_each_profile_and_increases_fixed_income(
    profile,
    base_fixed_income,
    priority_fixed_income,
) -> None:
    normal = calculate_allocation(investment_capacity=1000, risk_profile=profile, financial_score=80)
    adjusted = calculate_allocation(
        investment_capacity=1000,
        risk_profile=profile,
        financial_score=80,
        emergency_reserve_priority=True,
    )

    assert normal["adjusted_risk_profile"] == adjusted["adjusted_risk_profile"] == profile
    assert _fixed_income_percentage(normal) == base_fixed_income
    assert _fixed_income_percentage(adjusted) == priority_fixed_income
    assert sum(item["percentage"] for item in normal["allocation"]) == Decimal("100.00")
    assert sum(item["percentage"] for item in adjusted["allocation"]) == Decimal("100.00")


@pytest.mark.parametrize("investment_capacity", [Decimal("0"), Decimal("1"), Decimal("1000000")])
def test_reserve_priority_handles_insufficient_and_excess_budget_without_changing_percentages(investment_capacity) -> None:
    result = calculate_allocation(
        investment_capacity=investment_capacity,
        risk_profile="moderate",
        financial_score=80,
        emergency_reserve_priority=True,
    )

    assert _fixed_income_percentage(result) == Decimal("43.00")
    assert sum(item["amount"] for item in result["allocation"]) == investment_capacity.quantize(Decimal("0.01"))


@pytest.mark.parametrize(
    ("reserve", "expected_priority", "expected_investment_percentage"),
    [
        (Decimal("8999.99"), True, Decimal("0.1000")),
        (Decimal("9000.00"), False, Decimal("0.20")),
        (Decimal("9000.01"), False, Decimal("0.20")),
    ],
    ids=["below-target", "at-target", "above-target"],
)
def test_budget_engine_uses_the_same_three_month_boundary(reserve, expected_priority, expected_investment_percentage) -> None:
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("3000"),
        emergency_reserve=reserve,
        has_debt_default=False,
        financial_score=80,
    )

    assert result["emergency_reserve_priority"] is expected_priority
    assert result["investment_percentage"] == expected_investment_percentage


@pytest.mark.asyncio
async def test_missing_eligible_investments_keeps_reserve_allocation_and_warning(monkeypatch) -> None:
    async def fake_context(_session, *, user_id):
        assert user_id == 36
        return {
            "financial_score": 80,
            "investment_capacity": Decimal("1000"),
            "risk_profile": "moderate",
            "emergency_reserve_priority": True,
            "high_risk_allowed": True,
            "has_debt_default": False,
            "emergency_reserve_months": Decimal("2"),
            "monthly_salary": Decimal("5000"),
        }

    async def fake_assets(_session):
        return {asset_class: [] for asset_class in intelligence_service.ASSET_CLASSES}

    monkeypatch.setattr(intelligence_service, "get_financial_context", fake_context)
    monkeypatch.setattr(intelligence_service, "_read_assets_by_class", fake_assets)

    result = await intelligence_service.build_recommendation_base(object(), user_id=36)

    assert _fixed_income_percentage(result) == Decimal("43.00")
    assert all(not item["assets"] for item in result["recommendations_by_class"])
    assert any("Reserva de emergência" in warning for warning in result["warnings"])
    assert "dados de fundamentos ainda não disponíveis" in result["warnings"]
