from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.investor_profile_service import AGGRESSIVE, CONSERVATIVE, MODERATE, calculate_profile_score
from backend.app.intelligence.services.recommendation_score_service import calculate_recommendation_score


def _score(
    ticker: str = "AAA11",
    *,
    score_total: str = "80",
    score_value: str = "70",
    score_quality: str = "70",
    score_dividend: str = "60",
    score_liquidity: str = "70",
    score_risk: str = "80",
    price: str = "50",
):
    return SimpleNamespace(
        ticker=ticker,
        market="FII",
        date=date(2026, 6, 17),
        score_total=Decimal(score_total),
        score_value=Decimal(score_value),
        score_quality=Decimal(score_quality),
        score_dividend=Decimal(score_dividend),
        score_liquidity=Decimal(score_liquidity),
        score_risk=Decimal(score_risk),
        price=Decimal(price),
    )


def _guardrail(status: str = "APPROVED", risk_level: str = "LOW"):
    return SimpleNamespace(status=status, risk_level=risk_level, reasons_json={"summary": []})


def _trend(label: str = "UPTREND", momentum: str = "80", confidence: str = "HIGH", method: str = "ADAPTIVE_30D"):
    return SimpleNamespace(
        trend_label=label,
        momentum_score=Decimal(momentum),
        metadata_json={"confidence_level": confidence, "trend_method": method},
    )


def _calc(asset, guardrail=None, trend=None, profile=MODERATE):
    guardrail = guardrail or _guardrail()
    return calculate_recommendation_score(
        score_total=asset.score_total,
        profile_score=calculate_profile_score(asset, profile),
        status=guardrail.status,
        risk_level=guardrail.risk_level,
        trend_label=getattr(trend, "trend_label", None) if trend is not None else None,
        momentum_score=getattr(trend, "momentum_score", None) if trend is not None else None,
        trend_confidence=(getattr(trend, "metadata_json", {}) or {}).get("confidence_level") if trend is not None else None,
        profile=profile,
    )


def test_recommendation_score_stays_between_0_and_100() -> None:
    score = _calc(
        _score(score_total="100", score_value="100", score_quality="100", score_dividend="100", score_liquidity="100", score_risk="100"),
        trend=_trend(momentum="100"),
    )

    assert Decimal("0") <= score <= Decimal("100")


def test_uptrend_increases_score_and_downtrend_reduces_score() -> None:
    asset = _score()
    up = _calc(asset, trend=_trend("UPTREND", "80", "HIGH"))
    down = _calc(asset, trend=_trend("DOWNTREND", "80", "HIGH"))

    assert up > down


def test_confidence_high_improves_and_low_reduces_score() -> None:
    asset = _score()
    high = _calc(asset, trend=_trend("UPTREND", "70", "HIGH"))
    low = _calc(asset, trend=_trend("UPTREND", "70", "LOW"))

    assert high > low


def test_warning_reduces_score_via_safety_score() -> None:
    asset = _score()
    approved = _calc(asset, guardrail=_guardrail("APPROVED", "LOW"), trend=_trend())
    warning = _calc(asset, guardrail=_guardrail("WARNING", "HIGH"), trend=_trend())

    assert warning < approved


def test_conservative_uses_profile_safety_and_momentum() -> None:
    safe = _score("SAFE11", score_total="70", score_quality="95", score_liquidity="95", score_risk="95")
    risky = _score("RISK11", score_total="95", score_quality="30", score_liquidity="30", score_risk="30")

    safe_score = _calc(safe, guardrail=_guardrail("APPROVED", "LOW"), trend=_trend("SIDEWAYS", "55", "HIGH"), profile=CONSERVATIVE)
    risky_score = _calc(risky, guardrail=_guardrail("WARNING", "HIGH"), trend=_trend("UPTREND", "90", "HIGH"), profile=CONSERVATIVE)

    assert safe_score > risky_score


def test_aggressive_allows_warning_but_penalizes_safety() -> None:
    asset = _score(score_total="90", score_value="95", score_dividend="90")
    approved = _calc(asset, guardrail=_guardrail("APPROVED", "LOW"), trend=_trend(), profile=AGGRESSIVE)
    warning = _calc(asset, guardrail=_guardrail("WARNING", "HIGH"), trend=_trend(), profile=AGGRESSIVE)

    assert warning < approved


def test_budget_advisor_returns_trend_fields_and_orders_by_recommendation_score() -> None:
    items = build_budget_items(
        [
            _score("AAA11", score_total="95", score_quality="40", score_liquidity="40", score_risk="55"),
            _score("BBB11", score_total="80", score_quality="90", score_liquidity="90", score_risk="90"),
        ],
        budget=Decimal("150"),
        limit=20,
        profile=CONSERVATIVE,
        trend_signals={
            "AAA11": _trend("SIDEWAYS", "40", "LOW", "ADAPTIVE_SHORT"),
            "BBB11": _trend("UPTREND", "80", "HIGH", "ADAPTIVE_30D"),
        },
    )

    assert [item.ticker for item in items] == ["BBB11", "AAA11"]
    assert all(item.recommendation_score is not None for item in items)
    assert items[0].recommendation_score >= items[1].recommendation_score
    assert items[0].trend_label == "UPTREND"
    assert items[0].momentum_score == Decimal("80")
    assert items[0].trend_confidence == "HIGH"
    assert items[0].trend_method == "ADAPTIVE_30D"


def test_budget_advisor_does_not_break_without_trend_data() -> None:
    items = build_budget_items([_score("AAA11"), _score("BBB11", score_total="75")], budget=Decimal("150"), limit=20)

    assert len(items) == 2
    assert all(item.profile == MODERATE for item in items)
    assert all(item.recommendation_score is not None for item in items)
    assert all(item.trend_confidence == "VERY_LOW" for item in items)


def test_trend_filter_allowed_tickers_still_filters_correctly() -> None:
    items = build_budget_items(
        [_score("AAA11"), _score("BBB11")],
        budget=Decimal("150"),
        limit=20,
        allowed_tickers={"BBB11"},
        trend_signals={"BBB11": _trend("UPTREND", "80", "HIGH")},
    )

    assert [item.ticker for item in items] == ["BBB11"]
