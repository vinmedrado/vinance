from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.trend_signal_service import (
    DOWNTREND,
    INSUFFICIENT_HISTORY,
    UPTREND,
    PricePoint,
    calculate_trend_for_points,
    calculate_trends_for_rows,
)


def _score(ticker: str, score_total: str = "90", price: str = "50"):
    return SimpleNamespace(
        ticker=ticker,
        market="FII",
        date=date(2026, 6, 17),
        score_total=Decimal(score_total),
        price=Decimal(price),
        score_value=Decimal("60"),
        score_quality=Decimal("70"),
        score_dividend=Decimal("50"),
        score_liquidity=Decimal("80"),
        score_risk=Decimal("90"),
    )


def _points(ticker: str, prices: list[str], *, start: date = date(2026, 5, 1)) -> list[PricePoint]:
    return [PricePoint(ticker, start + timedelta(days=index), Decimal(price)) for index, price in enumerate(prices)]


def test_two_observations_returns_insufficient_history() -> None:
    payload = calculate_trend_for_points(_points("AAA11", ["100", "105"]), "FII")

    assert payload is not None
    assert payload["return_1d"] == Decimal("5.000000")
    assert payload["trend_label"] == INSUFFICIENT_HISTORY
    assert payload["metadata_json"]["observations_count"] == 2
    assert payload["metadata_json"]["confidence_level"] == "VERY_LOW"
    assert payload["metadata_json"]["trend_method"] == "INSUFFICIENT_HISTORY"


def test_three_observations_returns_short_trend_with_low_confidence() -> None:
    payload = calculate_trend_for_points(_points("AAA11", ["100", "103", "106"]), "FII")

    assert payload is not None
    assert payload["trend_label"] == UPTREND
    assert payload["metadata_json"]["observations_count"] == 3
    assert payload["metadata_json"]["confidence_level"] == "LOW"
    assert payload["metadata_json"]["trend_method"] == "ADAPTIVE_SHORT"
    assert payload["metadata_json"]["short_return"] is not None


def test_seven_observations_uses_7d_method_with_medium_confidence() -> None:
    payload = calculate_trend_for_points(_points("AAA11", ["100", "101", "102", "103", "104", "105", "108"]), "FII")

    assert payload is not None
    assert payload["trend_label"] == UPTREND
    assert payload["return_7d"] is not None
    assert payload["metadata_json"]["observations_count"] == 7
    assert payload["metadata_json"]["confidence_level"] == "MEDIUM"
    assert payload["metadata_json"]["trend_method"] == "ADAPTIVE_7D"


def test_thirty_observations_uses_30d_method_with_high_confidence() -> None:
    prices = [str(100 + index) for index in range(30)]
    payload = calculate_trend_for_points(_points("AAA11", prices), "FII")

    assert payload is not None
    assert payload["trend_label"] == UPTREND
    assert payload["return_7d"] is not None
    assert payload["return_30d"] is not None
    assert payload["metadata_json"]["observations_count"] == 30
    assert payload["metadata_json"]["confidence_level"] == "HIGH"
    assert payload["metadata_json"]["trend_method"] == "ADAPTIVE_30D"


def test_metadata_contains_adaptive_fields() -> None:
    payload = calculate_trend_for_points(_points("AAA11", ["100", "99", "101"]), "FII")

    assert payload is not None
    metadata = payload["metadata_json"]
    assert "observations_count" in metadata
    assert "trend_method" in metadata
    assert "confidence_level" in metadata


def test_returns_null_when_history_is_insufficient_for_horizon() -> None:
    payload = calculate_trend_for_points([PricePoint("AAA11", date(2026, 6, 17), Decimal("100"))], "FII")

    assert payload is not None
    assert payload["return_7d"] is None
    assert payload["return_30d"] is None
    assert payload["trend_label"] == INSUFFICIENT_HISTORY


def test_trend_labels_uptrend_and_downtrend_with_short_history() -> None:
    up = calculate_trend_for_points(_points("UP11", ["100", "105", "110"]), "FII")
    down = calculate_trend_for_points(_points("DN11", ["110", "100", "90"]), "FII")

    assert up is not None and up["trend_label"] == UPTREND
    assert down is not None and down["trend_label"] == DOWNTREND


def test_calculate_trends_groups_by_ticker_for_upsert_payloads() -> None:
    rows = [
        SimpleNamespace(ticker="AAA11", date=date(2026, 6, 10), price=Decimal("100")),
        SimpleNamespace(ticker="AAA11", date=date(2026, 6, 17), price=Decimal("105")),
        SimpleNamespace(ticker="BBB11", date=date(2026, 6, 17), price=Decimal("50")),
    ]

    payloads = calculate_trends_for_rows(rows, "FII")

    assert len(payloads) == 2
    assert {item["ticker"] for item in payloads} == {"AAA11", "BBB11"}


def test_budget_advisor_without_trend_filter_continues_equal() -> None:
    items = build_budget_items([_score("AAA11"), _score("BBB11", "80")], budget=Decimal("150"), limit=20)

    assert [item.ticker for item in items] == ["AAA11", "BBB11"]


def test_budget_advisor_with_trend_filter_filters_allowed_tickers() -> None:
    items = build_budget_items(
        [_score("AAA11"), _score("BBB11", "95")],
        budget=Decimal("150"),
        limit=20,
        allowed_tickers={"AAA11"},
    )

    assert [item.ticker for item in items] == ["AAA11"]
