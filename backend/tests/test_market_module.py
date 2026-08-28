from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from backend.app.core.database import get_session
from backend.app.main import app
from backend.app.market import service
from backend.app.market.models import AssetPrice, MacroIndicator, RendaFixaProduto
from backend.app.market.schemas import AssetPriceIn, normalize_ticker
from backend.app.market.scheduler import tasks


def _stamp():
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


def _price(**overrides):
    base = {
        "id": 1,
        "ticker": "PETR4",
        "market": "acoes",
        "date": date(2026, 5, 29),
        "open": Decimal("30.00"),
        "high": Decimal("31.00"),
        "low": Decimal("29.50"),
        "close": Decimal("30.50"),
        "volume": Decimal("100000"),
        "source": "test",
        "created_at": _stamp(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _macro(**overrides):
    base = {"id": 1, "code": "SELIC", "name": "Taxa Selic Meta", "date": date(2026, 5, 1), "value": Decimal("10.50"), "source": "test", "created_at": _stamp()}
    base.update(overrides)
    return SimpleNamespace(**base)


def _renda_fixa(**overrides):
    base = {
        "id": 1,
        "nome": "Tesouro Selic 2029",
        "emissor": "Tesouro Nacional",
        "tipo": "tesouro_direto",
        "indexador": "SELIC",
        "taxa_juros": Decimal("0.10"),
        "taxa_total_equiv": Decimal("10.60"),
        "vencimento": date(2029, 3, 1),
        "liquidez_dias": 1,
        "investimento_minimo": Decimal("150.00"),
        "garantia_fgc": False,
        "codigo_tesouro": "123",
        "selic_vigente": Decimal("10.50"),
        "ipca_12m": Decimal("4.20"),
        "source": "test",
        "coletado_em": _stamp(),
        "is_active": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


async def _fake_session():
    yield object()


def _install_overrides():
    app.dependency_overrides[get_session] = _fake_session


def _clear_overrides():
    app.dependency_overrides.clear()


def test_market_models_metadata_contains_expected_tables():
    assert AssetPrice.__tablename__ == "asset_prices"
    assert MacroIndicator.__tablename__ == "macro_indicators"
    assert RendaFixaProduto.__tablename__ == "renda_fixa_produtos"
    constraints = {constraint.name for constraint in AssetPrice.__table__.constraints}
    assert "uq_asset_prices_ticker_market_date_source" in constraints


def test_price_schema_normalizes_ticker_uppercase():
    payload = AssetPriceIn(ticker=" petr4 ", market="acoes", date=date(2026, 5, 29), close=Decimal("30.50"), source="TEST")
    assert payload.ticker == "PETR4"
    assert payload.source == "test"
    assert normalize_ticker(" mxrf11 ") == "MXRF11"


def test_bulk_insert_batch_size_limit():
    records = [{"id": index} for index in range(1001)]
    batches = list(service.chunk_records(records, batch_size=500))
    assert [len(batch) for batch in batches] == [500, 500, 1]
    with pytest.raises(ValueError):
        list(service.chunk_records(records, batch_size=501))


@pytest.mark.asyncio
async def test_bulk_upsert_does_not_duplicate(monkeypatch):
    class FakeResult:
        def __init__(self, obj):
            self.obj = obj
        def scalar_one_or_none(self):
            return self.obj

    class FakeSession:
        def __init__(self):
            self.added = []
            self.commits = 0
            self.calls = 0
        async def execute(self, query):
            self.calls += 1
            if self.calls == 1:
                return FakeResult(None)
            return FakeResult(SimpleNamespace(open=None, high=None, low=None, close=Decimal("1"), volume=None))
        def add(self, obj):
            self.added.append(obj)
        async def commit(self):
            self.commits += 1

    session = FakeSession()
    row = {"ticker": "PETR4", "market": "acoes", "date": date(2026, 5, 29), "close": Decimal("30.50"), "source": "test"}
    summary = await service.bulk_upsert_asset_prices(session, prices=[row, row])
    assert summary["inserted"] == 1
    assert summary["updated"] == 1
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_cleanup_uses_two_year_ttl():
    class FakeResult:
        rowcount = 3
    class FakeSession:
        def __init__(self):
            self.executed = False
            self.committed = False
        async def execute(self, query):
            self.executed = True
            return FakeResult()
        async def commit(self):
            self.committed = True
    session = FakeSession()
    deleted = await service.cleanup_asset_prices_older_than_2_years(session, reference_date=date(2026, 6, 1))
    assert deleted == 3
    assert session.executed is True
    assert session.committed is True


@pytest.mark.asyncio
async def test_macro_indicator_upsert_updates_existing():
    class FakeResult:
        def scalar_one_or_none(self):
            return SimpleNamespace(name="old", value=Decimal("1"))
    class FakeSession:
        async def execute(self, query):
            return FakeResult()
        def add(self, obj):
            raise AssertionError("existing indicator should not be inserted")
        async def commit(self):
            pass
        async def refresh(self, obj):
            pass
    indicator = await service.upsert_macro_indicator(
        FakeSession(),
        payload={"code": "SELIC", "name": "Taxa Selic Meta", "date": date(2026, 5, 1), "value": Decimal("10.50"), "source": "bcb"},
    )
    assert indicator.value == Decimal("10.50")


def test_market_macro_endpoint(monkeypatch):
    _install_overrides()
    async def fake_list_macro_indicators(session, *, code=None):
        return [_macro()], 1
    monkeypatch.setattr(service, "list_macro_indicators", fake_list_macro_indicators)
    with TestClient(app) as client:
        response = client.get("/api/v1/market/macro")
    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_market_prices_endpoint(monkeypatch):
    _install_overrides()
    async def fake_list_asset_prices(session, *, market, ticker, limit=365, offset=0):
        assert market == "acoes"
        assert ticker == "petr4"
        return [_price()], 1
    monkeypatch.setattr(service, "list_asset_prices", fake_list_asset_prices)
    with TestClient(app) as client:
        response = client.get("/api/v1/market/prices/acoes/petr4")
    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["items"][0]["ticker"] == "PETR4"


def test_market_renda_fixa_endpoint(monkeypatch):
    _install_overrides()
    async def fake_list_renda_fixa_produtos(session, *, is_active=True):
        return [_renda_fixa()], 1
    monkeypatch.setattr(service, "list_renda_fixa_produtos", fake_list_renda_fixa_produtos)
    with TestClient(app) as client:
        response = client.get("/api/v1/market/renda-fixa")
    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["items"][0]["tipo"] == "tesouro_direto"


def test_celery_tasks_import_without_error():
    assert tasks.sync_macro_indicators.name == "market.sync_macro_indicators"
    assert tasks.sync_tesouro_direto.name == "market.sync_tesouro_direto"
    assert tasks.sync_historical_prices_weekly.name == "market.sync_historical_prices_weekly"
    assert tasks.cleanup_old_asset_prices.name == "market.cleanup_old_asset_prices"
