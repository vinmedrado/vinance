from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.core.logging import get_logger
from backend.app.market.models import AcaoFundamental, FiiFundamental
from backend.app.market.normalizers.statusinvest import (
    SOURCE_HTML_FALLBACK,
    SOURCE_JSON,
    describe_payload,
    extract_rows,
    merge_html_fallback,
    normalize_acoes,
    normalize_fiis,
)
from backend.app.market.parsers.statusinvest_html import parse_acao_fallback, parse_fii_fallback
from backend.app.market.providers.statusinvest import StatusInvestClient
from backend.app.market.schemas import normalize_ticker

logger = get_logger(__name__)

STATUSINVEST_BATCH_SIZE = 300
STATUSINVEST_SOURCE_PREFIXES = {SOURCE_JSON, SOURCE_HTML_FALLBACK, "statusinvest_missing"}


def _chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    clean_size = max(1, min(size, STATUSINVEST_BATCH_SIZE))
    for index in range(0, len(items), clean_size):
        yield items[index : index + clean_size]


async def load_statusinvest_catalog_assets(
    session: AsyncSession,
    *,
    market: str,
    limit_assets: int | None = None,
) -> list[AssetCatalog]:
    normalized_market = "fii" if market == "fii" else "acoes"
    query = (
        select(AssetCatalog)
        .where(AssetCatalog.is_active.is_(True), AssetCatalog.market == normalized_market)
        .order_by(AssetCatalog.ticker.asc())
    )
    if limit_assets:
        query = query.limit(limit_assets)
    result = await session.execute(query)
    return list(result.scalars().all())


def _missing_fii_fallback_fields(item: dict[str, Any]) -> bool:
    return any(item.get(field) is None for field in ("vacancia_fisica", "vacancia_financeira", "gestora", "taxa_adm", "num_imoveis"))


def _missing_acao_fallback_fields(item: dict[str, Any]) -> bool:
    return any(item.get(field) is None for field in ("margem_liquida", "margem_ebitda", "divida_liq_ebitda", "ev_ebitda"))


def _log_statusinvest_payload(*, market: str, payload: Any, allowed_count: int, normalized_count: int) -> None:
    description = describe_payload(payload)
    logger.info(
        "Status Invest payload inspected",
        extra={
            "market": market,
            "allowed_tickers": allowed_count,
            "payload_type": description.get("payload_type"),
            "dict_keys": description.get("dict_keys"),
            "extracted_rows": description.get("row_count"),
            "normalized_rows": normalized_count,
            "first_row_keys": description.get("first_row_keys"),
        },
    )
    if description.get("row_count") == 0:
        logger.warning(
            "Status Invest payload extracted no rows",
            extra={
                "market": market,
                "reason": "no list found in known wrappers: data/list/results/items/result/stocks/funds",
                "payload_type": description.get("payload_type"),
                "dict_keys": description.get("dict_keys"),
            },
        )
    elif normalized_count == 0:
        sample_rows = extract_rows(payload)[:1]
        logger.warning(
            "Status Invest rows extracted but no catalog ticker matched",
            extra={
                "market": market,
                "allowed_tickers": allowed_count,
                "first_row_keys": list(sample_rows[0].keys())[:30] if sample_rows else [],
                "reason": "ticker aliases may not match catalog or fields changed upstream",
            },
        )


async def _apply_html_fallback(
    *,
    client: StatusInvestClient,
    item: dict[str, Any],
    market: str,
    enable_html_fallback: bool,
) -> tuple[dict[str, Any], str]:
    if not enable_html_fallback:
        return item, "json"
    if market == "fii" and not _missing_fii_fallback_fields(item):
        return item, "json"
    if market == "acoes" and not _missing_acao_fallback_fields(item):
        return item, "json"

    html = await client.get_asset_page(ticker=item["ticker"], market=market)
    fallback = parse_fii_fallback(html) if market == "fii" else parse_acao_fallback(html)
    return merge_html_fallback(item, fallback, market=market)


async def _bulk_upsert_fundamentals(
    session: AsyncSession,
    *,
    model,
    records: list[dict[str, Any]],
    batch_size: int = STATUSINVEST_BATCH_SIZE,
) -> dict[str, int]:
    summary = {"processed": 0, "inserted": 0, "updated": 0, "batches": 0}
    for batch in _chunks(records, batch_size):
        summary["batches"] += 1
        for record in batch:
            record = dict(record)
            record["ticker"] = normalize_ticker(record["ticker"])
            query = select(model).where(
                model.ticker == record["ticker"],
                model.date == record["date"],
                model.source == record["source"],
            )
            existing = (await session.execute(query)).scalar_one_or_none()
            if existing is None:
                session.add(model(**record))
                summary["inserted"] += 1
            else:
                for field, value in record.items():
                    setattr(existing, field, value)
                summary["updated"] += 1
            summary["processed"] += 1
        await session.commit()
    return summary


async def sync_statusinvest_acoes_from_catalog(
    session: AsyncSession,
    *,
    client: StatusInvestClient | None = None,
    batch_size: int = STATUSINVEST_BATCH_SIZE,
    limit_assets: int | None = None,
    enable_html_fallback: bool = True,
    reference_date: date | None = None,
) -> dict[str, int]:
    client = client or StatusInvestClient()
    assets = await load_statusinvest_catalog_assets(session, market="acoes", limit_assets=limit_assets)
    allowed = {asset.ticker.upper(): asset for asset in assets}
    summary = {
        "assets": len(assets),
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "failed_batches": 0,
        "json": 0,
        "html_fallback": 0,
        "missing": 0,
    }
    for batch in _chunks(assets, batch_size):
        tickers = {asset.ticker.upper() for asset in batch}
        payload = await client.get_acoes_batch([asset.ticker for asset in batch])
        if payload.get("error"):
            summary["failed_batches"] += 1
            continue
        rows = normalize_acoes(payload, allowed_tickers=tickers, reference_date=reference_date)
        _log_statusinvest_payload(market="acoes", payload=payload, allowed_count=len(tickers), normalized_count=len(rows))
        records: list[dict[str, Any]] = []
        for row in rows:
            row["name"] = allowed.get(row["ticker"]).name if allowed.get(row["ticker"]) else row["name"]
            try:
                final_row, confidence = await _apply_html_fallback(client=client, item=row, market="acoes", enable_html_fallback=enable_html_fallback)
                summary[confidence] += 1
                records.append(final_row)
            except Exception as exc:  # noqa: BLE001 - partial failures cannot break the batch
                summary["missing"] += 1
                logger.warning("Status Invest ação fallback failed", extra={"ticker": row.get("ticker"), "error": str(exc)})
        persisted = await _bulk_upsert_fundamentals(session, model=AcaoFundamental, records=records, batch_size=batch_size)
        summary["processed"] += persisted["processed"]
        summary["inserted"] += persisted["inserted"]
        summary["updated"] += persisted["updated"]
        await asyncio.sleep(1.0)
    logger.info("Status Invest ações fundamentals sync finished", extra=summary)
    return summary


async def sync_statusinvest_fiis_from_catalog(
    session: AsyncSession,
    *,
    client: StatusInvestClient | None = None,
    batch_size: int = STATUSINVEST_BATCH_SIZE,
    limit_assets: int | None = None,
    enable_html_fallback: bool = True,
    reference_date: date | None = None,
) -> dict[str, int]:
    client = client or StatusInvestClient()
    assets = await load_statusinvest_catalog_assets(session, market="fii", limit_assets=limit_assets)
    allowed = {asset.ticker.upper(): asset for asset in assets}
    summary = {
        "assets": len(assets),
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "failed_batches": 0,
        "json": 0,
        "html_fallback": 0,
        "missing": 0,
    }
    for batch in _chunks(assets, batch_size):
        tickers = {asset.ticker.upper() for asset in batch}
        payload = await client.get_fiis_batch([asset.ticker for asset in batch])
        if payload.get("error"):
            summary["failed_batches"] += 1
            continue
        rows = normalize_fiis(payload, allowed_tickers=tickers, reference_date=reference_date)
        _log_statusinvest_payload(market="fii", payload=payload, allowed_count=len(tickers), normalized_count=len(rows))
        records: list[dict[str, Any]] = []
        for row in rows:
            row["name"] = allowed.get(row["ticker"]).name if allowed.get(row["ticker"]) else row["name"]
            try:
                final_row, confidence = await _apply_html_fallback(client=client, item=row, market="fii", enable_html_fallback=enable_html_fallback)
                summary[confidence] += 1
                records.append(final_row)
            except Exception as exc:  # noqa: BLE001
                summary["missing"] += 1
                logger.warning("Status Invest FII fallback failed", extra={"ticker": row.get("ticker"), "error": str(exc)})
        persisted = await _bulk_upsert_fundamentals(session, model=FiiFundamental, records=records, batch_size=batch_size)
        summary["processed"] += persisted["processed"]
        summary["inserted"] += persisted["inserted"]
        summary["updated"] += persisted["updated"]
        await asyncio.sleep(1.0)
    logger.info("Status Invest FIIs fundamentals sync finished", extra=summary)
    return summary
