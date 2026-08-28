from datetime import datetime

from backend.app.market.providers.brapi import BrapiProvider


def test_importa_brapi_provider():
    assert BrapiProvider is not None


def test_normalize_quote_normaliza_payload_valido():
    provider = BrapiProvider(token="test-token")

    row = provider._normalize_quote(
        {
            "symbol": "PETR4",
            "regularMarketPrice": 37.15,
            "regularMarketChangePercent": 1.25,
            "regularMarketVolume": 123456789,
            "marketCap": 999999999,
        }
    )

    assert row is not None
    assert row["ticker"] == "PETR4"
    assert row["price"] == 37.15
    assert row["change_percent"] == 1.25
    assert row["volume"] == 123456789
    assert row["market_cap"] == 999999999
    assert isinstance(row["updated_at"], datetime)


def test_normalize_quote_retorna_none_com_payload_vazio():
    provider = BrapiProvider(token="test-token")

    assert provider._normalize_quote({}) is None


def test_fetch_quotes_divide_batches_de_20(monkeypatch):
    provider = BrapiProvider(token="test-token")
    calls = []

    def fake_fetch_batch(batch):
        calls.append(batch)
        return {
            "results": [
                {
                    "symbol": ticker,
                    "regularMarketPrice": 10.0,
                    "regularMarketChangePercent": 1.0,
                    "regularMarketVolume": 1000,
                    "marketCap": 100000,
                }
                for ticker in batch
            ]
        }

    monkeypatch.setattr(provider, "_fetch_batch", fake_fetch_batch)

    tickers = [f"TICK{i}" for i in range(45)]
    rows = provider.fetch_quotes(tickers)

    assert len(calls) == 3
    assert [len(batch) for batch in calls] == [20, 20, 5]
    assert len(rows) == 45
    assert rows[0]["ticker"] == "TICK0"


def test_fetch_quotes_lista_vazia_retorna_lista_vazia():
    provider = BrapiProvider(token="test-token")

    assert provider.fetch_quotes([]) == []
