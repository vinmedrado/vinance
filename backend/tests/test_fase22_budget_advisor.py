from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from backend.app.intelligence.services.budget_advisor_service import (
    DIVERSIFIED_ALLOCATION,
    build_budget_items,
)


def _score(ticker: str, score_total: str, price: str, market: str = "FII"):
    return SimpleNamespace(
        ticker=ticker,
        market=market,
        date=date(2026, 6, 17),
        score_total=Decimal(score_total),
        price=Decimal(price),
    )


def test_budget_150_returns_buyable_assets() -> None:
    items = build_budget_items(
        [_score("KNRI11", "91", "95"), _score("HGLG11", "80", "180")],
        budget=Decimal("150"),
        limit=20,
    )

    assert [item.ticker for item in items] == ["KNRI11"]
    assert items[0].quantity_possible == 1
    assert items[0].invested_amount == Decimal("95.00")


def test_does_not_return_zero_price_assets() -> None:
    items = build_budget_items(
        [_score("ZERO11", "99", "0"), _score("OK11", "88", "50")],
        budget=Decimal("150"),
        limit=20,
    )

    assert [item.ticker for item in items] == ["OK11"]


def test_quantity_possible_is_never_negative() -> None:
    items = build_budget_items(
        [_score("NEG11", "90", "-10"), _score("OK11", "75", "30")],
        budget=Decimal("150"),
        limit=20,
    )

    assert all(item.quantity_possible >= 0 for item in items)
    assert [item.ticker for item in items] == ["OK11"]


def test_ranking_ordered_by_score_total_desc() -> None:
    items = build_budget_items(
        [_score("B11", "70", "50"), _score("A11", "95", "50"), _score("C11", "80", "50")],
        budget=Decimal("150"),
        limit=20,
    )

    assert [item.ticker for item in items] == ["A11", "C11", "B11"]


def test_diversified_allocation_weights_sum_to_budget() -> None:
    budget = Decimal("500")
    allocated = sum((budget * weight).quantize(Decimal("0.01")) for weight in DIVERSIFIED_ALLOCATION.values())

    assert allocated == budget
    assert DIVERSIFIED_ALLOCATION == {
        "FII": Decimal("0.40"),
        "ACOES": Decimal("0.30"),
        "ETF": Decimal("0.20"),
        "BDR": Decimal("0.10"),
    }
