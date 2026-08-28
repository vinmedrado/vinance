from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.core.logging import get_logger
from backend.app.market import service as market_service
from backend.app.market.providers.brapi import BrapiClient

logger = get_logger(__name__)

BRAPI_MARKETS = ("acoes", "fii", "etf", "bdr")
MAX_BATCH_SIZE = 500
PROVIDER_BATCH_SIZE = 20
FII_BATCH_SIZE = 1


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _normalize_ticker(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_bad_request(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    status_code = payload.get("status_code") or payload.get("status")
    if status_code == 400 or str(status_code) == "400":
        return True
    error = str(payload.get("error") or "").lower()
    return "400" in error or "bad request" in error


def _normalize_quote_to_price(row: dict[str, Any], *, market: str) -> dict[str, Any] | None:
    ticker = _normalize_ticker(row.get("symbol") or row.get("ticker"))
    close = _decimal(row.get("regularMarketPrice") or row.get("close") or row.get("price"))
    if not ticker or close is None or close <= 0:
        return None
    return {
        "ticker": ticker,
        "market": market,
        "date": datetime.now(timezone.utc).date(),
        "open": _decimal(row.get("regularMarketOpen") or row.get("open")),
        "high": _decimal(row.get("regularMarketDayHigh") or row.get("high")),
        "low": _decimal(row.get("regularMarketDayLow") or row.get("low")),
        "close": close,
        "volume": _decimal(row.get("regularMarketVolume") or row.get("volume")),
        "source": "brapi",
    }


def normalize_brapi_quotes(payload: dict[str, Any], *, market_by_ticker: dict[str, str]) -> list[dict[str, Any]]:
    results = payload.get("results", []) if isinstance(payload, dict) else []
    normalized: list[dict[str, Any]] = []
    for row in results if isinstance(results, list) else []:
        if not isinstance(row, dict):
            continue
        ticker = _normalize_ticker(row.get("symbol") or row.get("ticker"))
        market = market_by_ticker.get(ticker)
        if not market:
            continue
        item = _normalize_quote_to_price(row, market=market)
        if item:
            normalized.append(item)
    return normalized


def normalize_brapi_historical(payload: dict[str, Any], *, ticker: str, market: str) -> list[dict[str, Any]]:
    results = payload.get("results", []) if isinstance(payload, dict) else []
    if not isinstance(results, list) or not results:
        return []
    historical = results[0].get("historicalDataPrice", []) if isinstance(results[0], dict) else []
    rows: list[dict[str, Any]] = []
    for row in historical if isinstance(historical, list) else []:
        if not isinstance(row, dict):
            continue
        close = _decimal(row.get("close"))
        raw_date = row.get("date")
        if close is None or close <= 0 or raw_date is None:
            continue
        try:
            parsed_date = datetime.fromtimestamp(int(raw_date), tz=timezone.utc).date() if isinstance(raw_date, int) else datetime.fromisoformat(str(raw_date)[:10]).date()
        except Exception:  # noqa: BLE001
            continue
        rows.append(
            {
                "ticker": ticker.upper(),
                "market": market,
                "date": parsed_date,
                "open": _decimal(row.get("open")),
                "high": _decimal(row.get("high")),
                "low": _decimal(row.get("low")),
                "close": close,
                "volume": _decimal(row.get("volume")),
                "source": "brapi",
            }
        )
    return rows


def _chunks(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _group_assets_by_market(assets: list[AssetCatalog]) -> dict[str, list[AssetCatalog]]:
    grouped: dict[str, list[AssetCatalog]] = defaultdict(list)
    for asset in assets:
        market = str(asset.market or "").strip().lower()
        if market in BRAPI_MARKETS:
            grouped[market].append(asset)
    return dict(grouped)


async def load_brapi_catalog_assets(session: AsyncSession, *, limit: int | None = None) -> list[AssetCatalog]:
    query = (
        select(AssetCatalog)
        .where(AssetCatalog.is_active.is_(True), AssetCatalog.market.in_(BRAPI_MARKETS))
        .order_by(AssetCatalog.market.asc(), AssetCatalog.ticker.asc())
    )
    if limit:
        query = query.limit(limit)
    result = await session.execute(query)
    return list(result.scalars().all())


async def _persist_quote_payload(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    assets: list[AssetCatalog],
) -> dict[str, int]:
    market_by_ticker = {_normalize_ticker(asset.ticker): str(asset.market).lower() for asset in assets}
    rows = normalize_brapi_quotes(payload, market_by_ticker=market_by_ticker)
    if not rows:
        return {"processed": 0, "inserted": 0, "updated": 0}
    persisted = await market_service.bulk_upsert_asset_prices(session, prices=rows, batch_size=MAX_BATCH_SIZE)
    return {
        "processed": persisted["processed"],
        "inserted": persisted["inserted"],
        "updated": persisted["updated"],
    }


async def _sync_single_ticker(
    session: AsyncSession,
    client: BrapiClient,
    asset: AssetCatalog,
    *,
    summary: dict[str, Any],
    reason: str,
) -> None:
    ticker = _normalize_ticker(asset.ticker)
    market = str(asset.market or "").lower()
    payload = await client.get_quotes([ticker])
    if payload.get("error"):
        summary["failed_tickers"].append(ticker)
        logger.warning(
            "Brapi ticker sync failed",
            extra={"market": market, "ticker": ticker, "reason": reason, "error": payload.get("error")},
        )
        return
    persisted = await _persist_quote_payload(session, payload, assets=[asset])
    summary["processed"] += persisted["processed"]
    summary["inserted"] += persisted["inserted"]
    summary["updated"] += persisted["updated"]
    if persisted["processed"] == 0:
        summary["invalid_tickers"].append(ticker)
    await asyncio.sleep(0.15)


async def _sync_market_quotes(
    session: AsyncSession,
    client: BrapiClient,
    *,
    market: str,
    assets: list[AssetCatalog],
    batch_size: int,
    summary: dict[str, Any],
) -> None:
    market_summary = summary["markets"].setdefault(
        market,
        {"assets": len(assets), "processed": 0, "failed": 0, "fallback_batches": 0, "mode": "ticker" if market == "fii" else "chunk"},
    )
    logger.info("Brapi market sync started", extra={"market": market, "assets": len(assets)})

    if market == "fii":
        for asset in assets:
            before_failed = len(summary["failed_tickers"])
            before_processed = summary["processed"]
            await _sync_single_ticker(session, client, asset, summary=summary, reason="fii_individual_mode")
            market_summary["processed"] += summary["processed"] - before_processed
            market_summary["failed"] += len(summary["failed_tickers"]) - before_failed
        logger.info("Brapi FII sync finished in individual mode", extra=market_summary | {"market": market})
        return

    chunk_size = max(1, min(batch_size, MAX_BATCH_SIZE))
    for batch in _chunks(assets, chunk_size):
        tickers = [_normalize_ticker(asset.ticker) for asset in batch]
        payload = await client.get_quotes(tickers)
        if payload.get("error") and _is_bad_request(payload):
            summary["fallback_batches"] += 1
            market_summary["fallback_batches"] += 1
            logger.warning(
                "Brapi chunk returned 400; falling back ticker by ticker",
                extra={"market": market, "tickers": tickers, "error": payload.get("error")},
            )
            for asset in batch:
                before_failed = len(summary["failed_tickers"])
                before_processed = summary["processed"]
                await _sync_single_ticker(session, client, asset, summary=summary, reason="chunk_400_fallback")
                market_summary["processed"] += summary["processed"] - before_processed
                market_summary["failed"] += len(summary["failed_tickers"]) - before_failed
            continue
        if payload.get("error"):
            summary["failed_batches"] += 1
            market_summary["failed"] += len(batch)
            summary["failed_tickers"].extend(tickers)
            logger.warning("Brapi chunk sync failed", extra={"market": market, "tickers": tickers, "error": payload.get("error")})
            continue
        persisted = await _persist_quote_payload(session, payload, assets=batch)
        summary["processed"] += persisted["processed"]
        summary["inserted"] += persisted["inserted"]
        summary["updated"] += persisted["updated"]
        market_summary["processed"] += persisted["processed"]
        returned_tickers = {_normalize_ticker(row.get("symbol") or row.get("ticker")) for row in payload.get("results", []) if isinstance(row, dict)}
        missing = [ticker for ticker in tickers if ticker not in returned_tickers]
        if missing:
            summary["invalid_tickers"].extend(missing)
        await asyncio.sleep(0.2)

    logger.info("Brapi market sync finished", extra=market_summary | {"market": market})


async def sync_brapi_quotes_from_catalog(
    session: AsyncSession,
    *,
    client: BrapiClient | None = None,
    batch_size: int = PROVIDER_BATCH_SIZE,
    limit_assets: int | None = None,
) -> dict[str, Any]:
    client = client or BrapiClient()
    assets = await load_brapi_catalog_assets(session, limit=limit_assets)
    grouped = _group_assets_by_market(assets)
    summary: dict[str, Any] = {
        "assets": len(assets),
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "failed_batches": 0,
        "fallback_batches": 0,
        "failed_tickers": [],
        "invalid_tickers": [],
        "markets": {},
    }

    for market in BRAPI_MARKETS:
        market_assets = grouped.get(market, [])
        if not market_assets:
            continue
        await _sync_market_quotes(
            session,
            client,
            market=market,
            assets=market_assets,
            batch_size=FII_BATCH_SIZE if market == "fii" else batch_size,
            summary=summary,
        )

    summary["failed_tickers"] = sorted(set(summary["failed_tickers"]))
    summary["invalid_tickers"] = sorted(set(summary["invalid_tickers"]) - set(summary["failed_tickers"]))
    logger.info("Brapi quotes sync finished", extra={k: v for k, v in summary.items() if k != "markets"})
    return summary


async def sync_brapi_historical_from_catalog(
    session: AsyncSession,
    *,
    client: BrapiClient | None = None,
    range: str = "3mo",  # noqa: A002
    limit_assets: int = 200,
) -> dict[str, int]:
    client = client or BrapiClient()
    assets = await load_brapi_catalog_assets(session, limit=limit_assets)
    summary = {"assets": len(assets), "processed": 0, "inserted": 0, "updated": 0, "failed_assets": 0}
    for asset in assets:
        payload = await client.get_historical_quotes(asset.ticker, range=range)
        if isinstance(payload, dict) and payload.get("error"):
            summary["failed_assets"] += 1
            continue
        rows = normalize_brapi_historical(payload, ticker=asset.ticker, market=asset.market)
        persisted = await market_service.bulk_upsert_asset_prices(session, prices=rows, batch_size=MAX_BATCH_SIZE)
        summary["processed"] += persisted["processed"]
        summary["inserted"] += persisted["inserted"]
        summary["updated"] += persisted["updated"]
    logger.info("Brapi historical sync finished", extra=summary)
    return summary
