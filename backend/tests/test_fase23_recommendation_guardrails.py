from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.recommendation_guardrail_model import AssetRecommendationGuardrail
from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.recommendation_guardrail_service import BLOCKED, WARNING, APPROVED, evaluate_guardrail


def _score(ticker: str = "AAA11", market: str = "FII", score_total: str = "90", price: str = "100"):
    return SimpleNamespace(
        ticker=ticker,
        market=market,
        date=date(2026, 6, 17),
        score_total=Decimal(score_total),
        price=Decimal(price),
    )


def _fii(**kwargs):
    base = {
        "ticker": "AAA11",
        "pvp": Decimal("0.90"),
        "dy_12m": Decimal("10"),
        "liquidez_diaria": Decimal("500000"),
        "num_cotistas": 20000,
        "vacancia_fisica": Decimal("5"),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _guardrail(ticker: str, status: str, risk_level: str = "LOW"):
    return SimpleNamespace(
        ticker=ticker,
        status=status,
        risk_level=risk_level,
        reasons_json={"blocked": [], "warnings": [status], "summary": [status]},
    )


def test_hctr11_deva11_warning_or_blocked_when_criteria_match() -> None:
    hctr = evaluate_guardrail(_score("HCTR11"), _fii(ticker="HCTR11", dy_12m=Decimal("22")))
    deva = evaluate_guardrail(_score("DEVA11"), _fii(ticker="DEVA11", pvp=Decimal("0.40")))

    assert hctr.status in {WARNING, BLOCKED}
    assert deva.status in {WARNING, BLOCKED}


def test_price_zero_becomes_blocked() -> None:
    decision = evaluate_guardrail(_score(price="0"), _fii())

    assert decision.status == BLOCKED
    assert "INVALID_PRICE" in decision.reasons_json["summary"]


def test_extreme_dy_becomes_blocked() -> None:
    decision = evaluate_guardrail(_score(), _fii(dy_12m=Decimal("35")))

    assert decision.status == BLOCKED
    assert "EXTREME_DY" in decision.reasons_json["summary"]


def test_budget_advisor_never_returns_blocked() -> None:
    scores = [_score("AAA11", score_total="95", price="50"), _score("BBB11", score_total="90", price="50")]
    guardrails = {"AAA11": _guardrail("AAA11", BLOCKED), "BBB11": _guardrail("BBB11", APPROVED)}

    items = build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails)

    assert [item.ticker for item in items] == ["BBB11"]
    assert all(item.status != BLOCKED for item in items)


def test_include_warnings_true_returns_approved_and_warning() -> None:
    scores = [_score("AAA11", score_total="95", price="50"), _score("BBB11", score_total="90", price="50")]
    guardrails = {"AAA11": _guardrail("AAA11", WARNING, "MEDIUM"), "BBB11": _guardrail("BBB11", APPROVED)}

    items = build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails, include_warnings=True)

    assert [item.ticker for item in items] == ["BBB11", "AAA11"]
    assert {item.status for item in items} == {APPROVED, WARNING}
    assert items[0].recommendation_score > items[1].recommendation_score


def test_include_warnings_false_returns_only_approved() -> None:
    scores = [_score("AAA11", score_total="95", price="50"), _score("BBB11", score_total="90", price="50")]
    guardrails = {"AAA11": _guardrail("AAA11", WARNING, "MEDIUM"), "BBB11": _guardrail("BBB11", APPROVED)}

    items = build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails, include_warnings=False)

    assert [item.ticker for item in items] == ["BBB11"]
    assert all(item.status == APPROVED for item in items)


def test_guardrails_table_unique_constraint_exists() -> None:
    constraints = {constraint.name for constraint in AssetRecommendationGuardrail.__table__.constraints}
    assert "uq_asset_recommendation_guardrails_ticker_market_date_source" in constraints
