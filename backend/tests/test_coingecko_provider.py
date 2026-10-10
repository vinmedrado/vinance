from datetime import datetime

import pytest

from backend.app.market.providers.coingecko import CoinGeckoProvider


def test_import_coingecko_provider():
    assert CoinGeckoProvider is not None


def test_normalize_market_valid_payload():
    provider = CoinGeckoProvider()

    normalized = provider._normalize_market({
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "current_price": 350000.0,
        "market_cap": 1_000_000_000_000,
        "total_volume": 50_000_000_000,
        "price_change_percentage_24h_in_currency": 1.2,
        "price_change_percentage_7d_in_currency": 5.4,
        "price_change_percentage_30d_in_currency": -2.1,
    })

    assert normalized is not None
    assert normalized["id"] == "bitcoin"
    assert normalized["symbol"] == "BTC"
    assert normalized["name"] == "Bitcoin"
    assert normalized["price"] == 350000.0
    assert normalized["market_cap"] == 1_000_000_000_000
    assert normalized["volume_24h"] == 50_000_000_000
    assert normalized["change_24h"] == 1.2
    assert normalized["change_7d"] == 5.4
    assert normalized["change_30d"] == -2.1
    assert normalized["source"] == "COINGECKO"
    assert isinstance(normalized["updated_at"], datetime)


def test_normalize_market_returns_none_with_empty_payload():
    provider = CoinGeckoProvider()
    assert provider._normalize_market({}) is None


def test_normalize_market_returns_none_without_current_price():
    provider = CoinGeckoProvider()
    assert provider._normalize_market({"id": "bitcoin", "symbol": "btc"}) is None


def test_fetch_markets_empty_ids_returns_empty_list():
    provider = CoinGeckoProvider()
    assert provider.fetch_markets([]) == []


def test_fetch_markets_uses_ids_correctly_with_monkeypatch(monkeypatch):
    provider = CoinGeckoProvider()
    captured = {}

    def fake_fetch(ids, vs_currency):
        captured["ids"] = ids
        captured["vs_currency"] = vs_currency
        return [{
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 350000.0,
        }]

    monkeypatch.setattr(provider, "_fetch_markets_payload", fake_fetch)

    result = provider.fetch_markets([" Bitcoin ", "ethereum", "bitcoin", ""], vs_currency="brl")

    assert captured["ids"] == ["bitcoin", "ethereum"]
    assert captured["vs_currency"] == "brl"
    assert len(result) == 1
    assert result[0]["id"] == "bitcoin"


def test_fetch_markets_page_payload_uses_expected_pagination_params(monkeypatch):
    provider = CoinGeckoProvider()
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return [{"id": "bitcoin", "symbol": "btc", "current_price": 350000.0}]

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params):
            captured["url"] = url
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr("backend.app.market.providers.coingecko.httpx.Client", FakeClient)

    payload = provider._fetch_markets_page_payload(vs_currency="brl", per_page=250, page=3)

    assert payload[0]["id"] == "bitcoin"
    assert captured["url"].endswith("/coins/markets")
    assert captured["params"] == {
        "vs_currency": "brl",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 3,
        "sparkline": "false",
        "price_change_percentage": "24h,7d,30d",
    }


def test_fetch_markets_by_pages_aggregates_results_and_continues_after_page_failure(monkeypatch):
    provider = CoinGeckoProvider()

    def fake_page(*, vs_currency, per_page, page):
        if page == 2:
            raise RuntimeError("page down")
        return [{
            "id": f"coin-{page}",
            "symbol": f"c{page}",
            "name": f"Coin {page}",
            "current_price": page,
        }]

    monkeypatch.setattr(provider, "_fetch_markets_page_payload", fake_page)

    result = provider.fetch_markets_by_pages(vs_currency="brl", per_page=250, pages=3)

    assert [item["id"] for item in result] == ["coin-1", "coin-3"]
    assert provider.last_page_errors == [{"page": 2, "error": "page down"}]
