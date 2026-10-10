from datetime import datetime

import pytest

from backend.app.market.services.coingecko_sync import CoinGeckoSyncService


class FakeScalarResult:
    def __init__(self, instance=None):
        self.instance = instance

    def scalar_one_or_none(self):
        return self.instance


class FakeSession:
    def __init__(self):
        self.added = []
        self.committed = False
        self.rolled_back = False
        self.executed = []

    def add(self, obj):
        self.added.append(obj)

    async def execute(self, stmt):
        self.executed.append(stmt)
        return FakeScalarResult()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeProvider:
    def __init__(self, payloads=None, error=None):
        self.payloads = payloads if payloads is not None else []
        self.error = error
        self.calls = []

    def fetch_markets(self, ids, vs_currency="brl"):
        self.calls.append((ids, vs_currency))
        if self.error:
            raise self.error
        return self.payloads


def fake_payload():
    return {
        "id": "bitcoin",
        "symbol": "BTC",
        "name": "Bitcoin",
        "price": 350000.0,
        "market_cap": 1000000000000,
        "volume_24h": 50000000000,
        "change_24h": 1.2,
        "change_7d": 5.4,
        "change_30d": -2.1,
        "updated_at": datetime.utcnow(),
        "source": "COINGECKO",
    }


def test_import_service():
    assert CoinGeckoSyncService is not None


@pytest.mark.asyncio
async def test_sync_markets_empty_returns_empty_summary():
    service = CoinGeckoSyncService(provider=FakeProvider())
    session = FakeSession()
    result = await service.sync_markets(session, [])

    assert result["source"] == "COINGECKO"
    assert result["mercado"] == "CRIPTO"
    assert result["status"] == "SUCCESS"
    assert result["total"] == 0
    assert result["ok"] == 0
    assert result["erros"] == 0
    assert session.committed is True


def test_map_fake_payload_works():
    service = CoinGeckoSyncService(provider=FakeProvider())
    mapped = service._map_payload(fake_payload(), vs_currency="brl")

    assert mapped["coin_id"] == "bitcoin"
    assert mapped["ticker"] == "BTC"
    assert mapped["name"] == "Bitcoin"
    assert str(mapped["price_brl"]) == "350000.0"
    assert str(mapped["market_cap_usd"]) == "1000000000000"
    assert str(mapped["volume_24h_usd"]) == "50000000000"
    assert str(mapped["price_change_24h_pct"]) == "1.2"
    assert str(mapped["price_change_7d_pct"]) == "5.4"
    assert str(mapped["price_change_30d_pct"]) == "-2.1"
    assert mapped["source"] == "COINGECKO"
    assert "date" in mapped
    assert "coletado_em" in mapped


@pytest.mark.asyncio
async def test_provider_mocked_returns_success_summary(monkeypatch):
    import backend.app.market.services.coingecko_sync as sync_module

    class FakeCryptoModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(sync_module, "CriptoFundamental", FakeCryptoModel)

    provider = FakeProvider(payloads=[fake_payload()])
    service = CoinGeckoSyncService(provider=provider)
    session = FakeSession()

    result = await service.sync_markets(session, ["bitcoin"], vs_currency="brl")

    assert provider.calls == [(["bitcoin"], "brl")]
    assert result["status"] == "SUCCESS"
    assert result["total"] == 1
    assert result["ok"] == 1
    assert result["erros"] == 0
    assert session.committed is True
    assert len(session.added) >= 1
    assert session.executed == []


@pytest.mark.asyncio
async def test_provider_error_returns_failed_summary():
    service = CoinGeckoSyncService(provider=FakeProvider(error=RuntimeError("api down")))
    session = FakeSession()

    result = await service.sync_markets(session, ["bitcoin"])

    assert result["status"] == "FAILED"
    assert result["total"] == 1
    assert result["ok"] == 0
    assert result["erros"] == 1
    assert result["error_message"] == "api down"
    assert session.rolled_back is True


def test_missing_model_fields_do_not_break():
    class Columns:
        def keys(self):
            return ["coin_id", "ticker", "date", "source", "price_brl"]

    class Table:
        columns = Columns()

    class DummyModel:
        __name__ = "DummyModel"
        __table__ = Table()

    service = CoinGeckoSyncService(provider=FakeProvider())
    filtered = service._filter_model_fields(
        DummyModel,
        {"coin_id": "bitcoin", "ticker": "BTC", "date": "2026-06-09", "source": "COINGECKO", "price_brl": 1, "campo_inexistente": 2},
    )

    assert filtered == {"coin_id": "bitcoin", "ticker": "BTC", "date": "2026-06-09", "source": "COINGECKO", "price_brl": 1}


class FakePagedProvider(FakeProvider):
    def __init__(self, payloads=None, page_errors=None):
        super().__init__(payloads=payloads)
        self.last_page_errors = page_errors or []
        self.page_calls = []

    def fetch_markets_by_pages(self, vs_currency="brl", per_page=250, pages=4):
        self.page_calls.append((vs_currency, per_page, pages))
        return self.payloads


@pytest.mark.asyncio
async def test_sync_markets_by_pages_uses_broad_catalog_and_persists(monkeypatch):
    import backend.app.market.services.coingecko_sync as sync_module

    class FakeCryptoModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(sync_module, "CriptoFundamental", FakeCryptoModel)

    provider = FakePagedProvider(payloads=[fake_payload()])
    service = CoinGeckoSyncService(provider=provider)
    session = FakeSession()

    result = await service.sync_markets_by_pages(session, vs_currency="brl", per_page=250, pages=4)

    assert provider.page_calls == [("brl", 250, 4)]
    assert result["status"] == "SUCCESS"
    assert result["total"] == 1
    assert result["ok"] == 1
    assert result["erros"] == 0
    assert result["pages"] == 4
    assert result["per_page"] == 250
    assert session.committed is True
    assert session.executed == []


@pytest.mark.asyncio
async def test_sync_markets_by_pages_partial_page_failure_does_not_break(monkeypatch):
    import backend.app.market.services.coingecko_sync as sync_module

    class FakeCryptoModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(sync_module, "CriptoFundamental", FakeCryptoModel)

    provider = FakePagedProvider(payloads=[fake_payload()], page_errors=[{"page": 2, "error": "timeout"}])
    service = CoinGeckoSyncService(provider=provider)
    session = FakeSession()

    result = await service.sync_markets_by_pages(session, vs_currency="brl", per_page=250, pages=4)

    assert result["status"] == "PARTIAL_SUCCESS"
    assert result["ok"] == 1
    assert result["erros"] == 1
    assert result["page_errors"] == [{"page": 2, "error": "timeout"}]


@pytest.mark.asyncio
async def test_crypto_sync_appends_intraday_snapshots_without_daily_upsert(monkeypatch):
    import backend.app.market.services.coingecko_sync as sync_module

    class FakeCryptoModel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(sync_module, "CriptoFundamental", FakeCryptoModel)

    provider = FakeProvider(payloads=[fake_payload(), fake_payload()])
    service = CoinGeckoSyncService(provider=provider)
    session = FakeSession()

    result = await service.sync_markets(session, ["bitcoin", "ethereum"], vs_currency="brl")

    assert result["status"] == "SUCCESS"
    assert len(session.added) >= 2
    assert session.executed == []
