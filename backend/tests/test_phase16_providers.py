from __future__ import annotations

from datetime import date

import httpx
import pytest

from backend.app.core.celery import celery_app
from backend.app.market.providers.brapi import BrapiClient
from backend.app.market.providers.coingecko import CoinGeckoClient
from backend.app.market.services.brapi_service import normalize_brapi_historical, normalize_brapi_quotes
from backend.app.market.services.coingecko_service import normalize_coingecko_market_data
from backend.app.market import service as market_service


def test_brapi_quote_normalization_uses_catalog_market_mapping():
    payload = {
        "results": [
            {"symbol": "PETR4", "regularMarketPrice": 38.5, "regularMarketVolume": 1000},
            {"symbol": "UNKNOWN", "regularMarketPrice": 10},
        ]
    }
    rows = normalize_brapi_quotes(payload, market_by_ticker={"PETR4": "acoes"})
    assert len(rows) == 1
    assert rows[0]["ticker"] == "PETR4"
    assert rows[0]["market"] == "acoes"
    assert rows[0]["source"] == "brapi"


def test_brapi_historical_normalization_parses_epoch_dates():
    payload = {"results": [{"historicalDataPrice": [{"date": 1717200000, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]}]}
    rows = normalize_brapi_historical(payload, ticker="HGLG11", market="fii")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "HGLG11"
    assert isinstance(rows[0]["date"], date)


def test_coingecko_market_normalization_outputs_prices_and_fundamentals():
    payload = [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 65000,
            "market_cap": 100000000,
            "market_cap_rank": 1,
            "total_volume": 5000000,
            "price_change_percentage_30d_in_currency": 3.5,
            "ath": 70000,
            "ath_change_percentage": -5,
        }
    ]
    prices, fundamentals = normalize_coingecko_market_data(payload, ticker_by_coin_id={"bitcoin": "BTC"})
    assert prices[0]["market"] == "cripto"
    assert prices[0]["source"] == "coingecko"
    assert fundamentals[0]["coin_id"] == "bitcoin"
    assert fundamentals[0]["ticker"] == "BTC"


@pytest.mark.asyncio
async def test_brapi_client_safe_get_handles_timeout(monkeypatch):
    client = BrapiClient(api_key="", min_interval_seconds=0)

    async def fail(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(client, "_get", fail)
    result = await client.safe_get("/quote/PETR4")
    assert result["results"] == []
    assert "error" in result


@pytest.mark.asyncio
async def test_coingecko_client_safe_get_handles_timeout(monkeypatch):
    client = CoinGeckoClient(api_key="", min_interval_seconds=0)

    async def fail(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(client, "_get", fail)
    result = await client.safe_get("/coins/markets")
    assert result == []


def test_chunk_records_rejects_oversized_batches():
    with pytest.raises(ValueError):
        list(market_service.chunk_records([{"x": 1}], batch_size=501))


def test_celery_schedule_contains_current_market_and_intelligence_chain():
    schedule = celery_app.conf.beat_schedule
    assert schedule["market-sync-cripto-coingecko-every-10-min"]["task"] == "market.sync_cripto_coingecko"
    assert schedule["market-sync-investidor10-daily-after-close"]["task"] == "market.sync_all_investidor10"
    assert schedule["market-calculate-asset-scores-daily-after-investidor10"]["task"] == "market.calculate_asset_scores"
    assert schedule["market-calculate-recommendation-guardrails-daily-after-scores"]["task"] == "market.calculate_recommendation_guardrails"
    assert schedule["market-calculate-trend-signals-daily-after-guardrails"]["task"] == "market.calculate_trend_signals"
    assert schedule["investment-alerts-evaluate-daily-after-intelligence"]["task"] == "investment_alerts.evaluate_subscriptions"
