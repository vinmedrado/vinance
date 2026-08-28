from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.services.recommendation_explanation_service import (
    build_recommendation_explanation,
    enrich_item_with_explanation,
)


def _item(**overrides):
    data = {
        "ticker": "CPTS11",
        "market": "FII",
        "price": Decimal("7.44"),
        "quantity_possible": 40,
        "invested_amount": Decimal("297.60"),
        "score_total": Decimal("82.10"),
        "profile": "CONSERVATIVE",
        "profile_score": Decimal("93.07"),
        "recommendation_score": Decimal("82.06"),
        "status": "APPROVED",
        "risk_level": "LOW",
        "score_quality": Decimal("98.66"),
        "score_liquidity": Decimal("95.27"),
        "score_risk": Decimal("87.24"),
        "score_dividend": Decimal("79.19"),
        "trend_label": "SIDEWAYS",
        "momentum_score": Decimal("42.32"),
        "trend_confidence": "MEDIUM",
        "trend_method": "ADAPTIVE_30D",
        "recommendation_components_json": {"base": "test"},
        "reasons_json": {"summary": []},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _context():
    return {
        "budget": Decimal("300"),
        "market": "FII",
        "profile": "CONSERVATIVE",
        "recommendation_rank": 1,
        "total_candidates": 20,
        "alternatives": [
            _item(ticker="BTCI11", recommendation_score=Decimal("77"), momentum_score=Decimal("35")),
            _item(ticker="XPML11", recommendation_score=Decimal("75"), momentum_score=Decimal("45")),
        ],
    }


def test_advanced_explanation_returns_executive_summary_and_decision_card() -> None:
    payload = build_recommendation_explanation(_item(), context=_context())

    assert "executive_summary" in payload
    assert payload["decision_card"]["ticker"] == "CPTS11"
    assert payload["decision_card"]["quantity"] == 40


def test_advanced_explanation_returns_score_breakdown_strengths_and_attention_points() -> None:
    payload = build_recommendation_explanation(_item(), context=_context())

    assert payload["score_breakdown"]["profile_score"] == Decimal("93.07")
    assert payload["strengths"]
    assert payload["attention_points"]
    assert payload["relative_position"]["rank"] == 1
    assert payload["relative_position"]["total_candidates"] == 20


def test_comparison_with_alternatives_exists_for_best_recommendation() -> None:
    payload = build_recommendation_explanation(_item(), context=_context(), summary=False)

    assert payload["comparison_with_alternatives"]
    assert payload["comparison_with_alternatives"][0]["ticker"] == "BTCI11"


def test_summary_alternative_keeps_contract_but_no_comparison() -> None:
    payload = build_recommendation_explanation(_item(ticker="BTCI11"), context={**_context(), "recommendation_rank": 2}, summary=True)

    assert payload["recommendation_title"].startswith("Alternativa")
    assert payload["comparison_with_alternatives"] == []


def test_explanation_does_not_use_forbidden_profit_guarantee_terms() -> None:
    payload = enrich_item_with_explanation(_item(), budget=Decimal("300"), context=_context())
    combined_text = " ".join(str(value).lower() for value in payload.values())

    assert "garantido" not in combined_text
    assert "certeza de lucro" not in combined_text


def test_explanation_quality_is_returned() -> None:
    payload = build_recommendation_explanation(_item(), context=_context())

    assert payload["explanation_quality"] in {"BASIC", "GOOD", "STRONG"}
