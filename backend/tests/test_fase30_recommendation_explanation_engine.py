from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.services.recommendation_explanation_service import (
    build_appreciation_text,
    build_recommendation_explanation,
    calculate_appreciation_signal,
    calculate_confidence_score,
    enrich_item_with_explanation,
)


def _item(**overrides):
    data = {
        "ticker": "CPTS11",
        "market": "FII",
        "price": Decimal("7.44"),
        "quantity_possible": 40,
        "invested_amount": Decimal("297.60"),
        "score_total": Decimal("82"),
        "profile": "CONSERVATIVE",
        "profile_score": Decimal("84"),
        "recommendation_score": Decimal("83"),
        "status": "APPROVED",
        "risk_level": "LOW",
        "trend_label": "UPTREND",
        "momentum_score": Decimal("55"),
        "trend_confidence": "MEDIUM",
        "trend_method": "ADAPTIVE_30D",
        "recommendation_components_json": {"base": "test"},
        "reasons_json": {"summary": []},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_explanation_contains_quantity_possible_and_budget_math() -> None:
    explanation = build_recommendation_explanation(_item(), budget=Decimal("300"))

    assert "40 cota(s)" in explanation["decision_summary"]
    assert explanation["remaining_budget"] == Decimal("2.40")
    assert explanation["budget_usage_pct"] == Decimal("99.20")


def test_appreciation_signal_high_moderate_low_unknown() -> None:
    assert calculate_appreciation_signal(
        recommendation_score=Decimal("85"), trend_label="UPTREND", momentum_score=Decimal("50"), trend_confidence="HIGH"
    ) == "HIGH"
    assert calculate_appreciation_signal(
        recommendation_score=Decimal("72"), trend_label="SIDEWAYS", momentum_score=Decimal("30"), trend_confidence="LOW"
    ) == "MODERATE"
    assert calculate_appreciation_signal(
        recommendation_score=Decimal("55"), trend_label="UPTREND", momentum_score=Decimal("70"), trend_confidence="HIGH"
    ) == "LOW"
    assert calculate_appreciation_signal(
        recommendation_score=Decimal("90"), trend_label="INSUFFICIENT_HISTORY", momentum_score=Decimal("90"), trend_confidence="VERY_LOW"
    ) == "UNKNOWN"


def test_confidence_score_stays_between_0_and_100() -> None:
    high = calculate_confidence_score(_item(recommendation_score=Decimal("98"), trend_confidence="HIGH"))
    low = calculate_confidence_score(_item(recommendation_score=Decimal("5"), status="WARNING", risk_level="HIGH", trend_confidence="LOW"))

    assert Decimal("0") <= high <= Decimal("100")
    assert Decimal("0") <= low <= Decimal("100")


def test_explanation_text_does_not_use_forbidden_guarantee_terms() -> None:
    payload = enrich_item_with_explanation(_item(), budget=Decimal("300"))
    combined_text = " ".join(str(value).lower() for value in payload.values())

    assert "garantido" not in combined_text
    assert "certeza de lucro" not in combined_text


def test_appreciation_text_is_cautious() -> None:
    text = build_appreciation_text("MODERATE", "SIDEWAYS", "MEDIUM")

    assert "sinal moderado" in text
    assert "sem garantia" in text
