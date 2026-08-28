from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.core.database import Base, get_session
from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.services import asset_score_service as service
from backend.app.main import app


def _row(ticker: str, **kwargs):
    base = {
        "ticker": ticker,
        "date": date(2026, 6, 16),
        "price": Decimal("10.00"),
        "pvp": Decimal("1.0"),
        "dy_12m": Decimal("8.0"),
        "liquidez_diaria": Decimal("1000000"),
        "num_cotistas": 10000,
        "vacancia_fisica": Decimal("5.0"),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_score_returns_between_0_and_100():
    rows = [_row("AAA11", pvp=Decimal("0.8")), _row("BBB11", pvp=Decimal("1.5"))]
    payloads = service.calculate_scores_for_rows(rows, "FII")
    assert payloads
    for payload in payloads:
        assert Decimal("0") <= payload["score_total"] <= Decimal("100")
        assert Decimal("0") <= payload["score_value"] <= Decimal("100")


def test_null_fields_do_not_break_score():
    rows = [_row("AAA11", pvp=None, dy_12m=None), _row("BBB11", liquidez_diaria=None, num_cotistas=None)]
    payloads = service.calculate_scores_for_rows(rows, "FII")
    assert len(payloads) == 2
    assert all(payload["score_total"] is not None for payload in payloads)
    assert all(Decimal("0") <= payload["score_total"] <= Decimal("100") for payload in payloads)


@pytest.mark.asyncio
async def test_ranking_orders_by_score_total_desc(monkeypatch):
    class Result:
        def __init__(self, value):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return [
                SimpleNamespace(ticker="AAA11", score_total=Decimal("99")),
                SimpleNamespace(ticker="BBB11", score_total=Decimal("80")),
            ]

    class FakeSession:
        async def execute(self, query):
            text = str(query)
            if "max" in text.lower():
                return Result(date(2026, 6, 16))
            return Result(None)

    rankings = await service.list_rankings(FakeSession(), market="FII", limit=20)
    assert [item.ticker for item in rankings] == ["AAA11", "BBB11"]


@pytest.mark.asyncio
async def test_upsert_does_not_duplicate(monkeypatch):
    calls = {"execute": 0, "commit": 0}

    class FakeSession:
        async def execute(self, stmt):
            calls["execute"] += 1

        async def commit(self):
            calls["commit"] += 1

    payload = service.calculate_scores_for_rows([_row("AAA11")], "FII")
    first = await service.upsert_asset_scores(FakeSession(), payload)
    second = await service.upsert_asset_scores(FakeSession(), payload)
    assert first == 1
    assert second == 1
    assert calls == {"execute": 2, "commit": 2}


def test_service_does_not_alter_fundamental_tables():
    tables = set(Base.metadata.tables.keys())
    assert "asset_scores" in tables
    assert {"fii_fundamentals", "acoes_fundamentals", "etf_fundamentals", "bdr_fundamentals"}.issubset(tables)
    for table_name in ("fii_fundamentals", "acoes_fundamentals", "etf_fundamentals", "bdr_fundamentals"):
        assert "score_total" not in Base.metadata.tables[table_name].columns


def test_asset_scores_unique_constraint_exists():
    constraints = {constraint.name for constraint in AssetScore.__table__.constraints}
    assert "uq_asset_scores_ticker_market_date_source" in constraints


async def _fake_session():
    yield object()


def test_rankings_endpoint(monkeypatch):
    async def fake_list_rankings(session, *, market, limit):
        assert market == "FII"
        return [
            SimpleNamespace(
                ticker="AAA11",
                market="FII",
                date=date(2026, 6, 16),
                score_total=Decimal("90"),
                score_value=Decimal("80"),
                score_quality=Decimal("70"),
                score_dividend=Decimal("95"),
                score_liquidity=Decimal("85"),
                score_risk=Decimal("75"),
                price=Decimal("10.00"),
                metadata_json={"coverage": 1},
            )
        ]

    app.dependency_overrides[get_session] = _fake_session
    monkeypatch.setattr("backend.app.intelligence.router.list_rankings", fake_list_rankings)
    with TestClient(app) as client:
        response = client.get("/api/intelligence/rankings?market=FII&limit=20")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()[0]["ticker"] == "AAA11"
