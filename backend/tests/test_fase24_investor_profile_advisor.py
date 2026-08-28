from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.investor_profile_service import (
    AGGRESSIVE,
    CONSERVATIVE,
    MODERATE,
    get_diversified_allocation,
    normalize_profile,
)
from backend.app.intelligence.services.recommendation_guardrail_service import APPROVED, BLOCKED, WARNING


def _score(ticker: str, score_total: str = "90", price: str = "50", **kwargs):
    base = {
        "ticker": ticker,
        "market": "FII",
        "date": date(2026, 6, 17),
        "score_total": Decimal(score_total),
        "price": Decimal(price),
        "score_value": Decimal("50"),
        "score_quality": Decimal("50"),
        "score_dividend": Decimal("50"),
        "score_liquidity": Decimal("50"),
        "score_risk": Decimal("80"),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _guardrail(ticker: str, status: str = APPROVED, risk_level: str = "LOW"):
    return SimpleNamespace(
        ticker=ticker,
        status=status,
        risk_level=risk_level,
        reasons_json={"blocked": [], "warnings": [], "summary": [status]},
    )


def test_without_profile_uses_moderate() -> None:
    items = build_budget_items([_score("AAA11")], budget=Decimal("150"), limit=20)

    assert items[0].profile == MODERATE
    assert items[0].profile_score == items[0].score_total


def test_invalid_profile_raises_value_error() -> None:
    with pytest.raises(ValueError):
        normalize_profile("INVALID")


def test_conservative_does_not_return_warning() -> None:
    scores = [_score("WARN11", score_total="99"), _score("OK11", score_total="80")]
    guardrails = {"WARN11": _guardrail("WARN11", WARNING, "MEDIUM"), "OK11": _guardrail("OK11", APPROVED, "LOW")}

    items = build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails, include_warnings=True, profile=CONSERVATIVE)

    assert [item.ticker for item in items] == ["OK11"]
    assert all(item.status == APPROVED and item.risk_level == "LOW" for item in items)


def test_aggressive_never_returns_blocked() -> None:
    scores = [_score("BLOCK11", score_total="99"), _score("WARN11", score_total="95")]
    guardrails = {"BLOCK11": _guardrail("BLOCK11", BLOCKED, "HIGH"), "WARN11": _guardrail("WARN11", WARNING, "HIGH")}

    items = build_budget_items(scores, budget=Decimal("150"), limit=20, guardrails=guardrails, include_warnings=True, profile=AGGRESSIVE)

    assert [item.ticker for item in items] == ["WARN11"]
    assert all(item.status != BLOCKED for item in items)


def test_diversified_allocation_changes_by_profile() -> None:
    conservative = get_diversified_allocation(CONSERVATIVE)
    aggressive = get_diversified_allocation(AGGRESSIVE)

    assert conservative == {
        "ETF": Decimal("0.50"),
        "FII": Decimal("0.30"),
        "ACOES": Decimal("0.20"),
        "BDR": Decimal("0.00"),
    }
    assert aggressive == {
        "ACOES": Decimal("0.30"),
        "FII": Decimal("0.25"),
        "ETF": Decimal("0.25"),
        "BDR": Decimal("0.20"),
    }
    assert conservative != aggressive


def test_existing_endpoint_behavior_still_supported_by_default_profile() -> None:
    items = build_budget_items([_score("AAA11", score_total="70"), _score("BBB11", score_total="90")], budget=Decimal("150"), limit=20)

    assert [item.ticker for item in items] == ["BBB11", "AAA11"]
    assert all(item.profile == MODERATE for item in items)
