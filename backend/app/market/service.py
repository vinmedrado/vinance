from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market.models import AssetPrice, MacroIndicator, RendaFixaProduto
from backend.app.market.schemas import AssetPriceIn, MacroIndicatorIn, RendaFixaProdutoIn, normalize_market, normalize_ticker

MAX_BULK_BATCH_SIZE = 500
PRICE_TTL_DAYS = 730


def chunk_records(records: list[dict], batch_size: int = MAX_BULK_BATCH_SIZE) -> Iterable[list[dict]]:
    if batch_size <= 0 or batch_size > MAX_BULK_BATCH_SIZE:
        raise ValueError("batch_size must be between 1 and 500")
    for index in range(0, len(records), batch_size):
        yield records[index : index + batch_size]


async def bulk_upsert_asset_prices(
    session: AsyncSession,
    *,
    prices: list[AssetPriceIn | dict],
    batch_size: int = MAX_BULK_BATCH_SIZE,
) -> dict[str, int]:
    payloads = [p.model_dump() if isinstance(p, AssetPriceIn) else AssetPriceIn(**p).model_dump() for p in prices]
    summary = {"processed": 0, "inserted": 0, "updated": 0, "batches": 0}

    for batch in chunk_records(payloads, batch_size=batch_size):
        summary["batches"] += 1
        for payload in batch:
            query = select(AssetPrice).where(
                AssetPrice.ticker == payload["ticker"],
                AssetPrice.market == payload["market"],
                AssetPrice.date == payload["date"],
                AssetPrice.source == payload["source"],
            )
            existing = (await session.execute(query)).scalar_one_or_none()
            if existing is None:
                session.add(AssetPrice(**payload))
                summary["inserted"] += 1
            else:
                for field in ("open", "high", "low", "close", "volume"):
                    setattr(existing, field, payload[field])
                summary["updated"] += 1
            summary["processed"] += 1
        await session.commit()
    return summary


async def cleanup_asset_prices_older_than_2_years(
    session: AsyncSession,
    *,
    reference_date: date | None = None,
) -> int:
    cutoff = (reference_date or datetime.now(timezone.utc).date()) - timedelta(days=PRICE_TTL_DAYS)
    result = await session.execute(delete(AssetPrice).where(AssetPrice.date < cutoff))
    await session.commit()
    return int(result.rowcount or 0)


async def upsert_macro_indicator(session: AsyncSession, *, payload: MacroIndicatorIn | dict) -> MacroIndicator:
    data = payload.model_dump() if isinstance(payload, MacroIndicatorIn) else MacroIndicatorIn(**payload).model_dump()
    query = select(MacroIndicator).where(
        MacroIndicator.code == data["code"],
        MacroIndicator.date == data["date"],
        MacroIndicator.source == data["source"],
    )
    existing = (await session.execute(query)).scalar_one_or_none()
    if existing is None:
        indicator = MacroIndicator(**data)
        session.add(indicator)
    else:
        existing.name = data["name"]
        existing.value = data["value"]
        indicator = existing
    await session.commit()
    await session.refresh(indicator)
    return indicator


async def upsert_renda_fixa_produto(session: AsyncSession, *, payload: RendaFixaProdutoIn | dict) -> RendaFixaProduto:
    data = payload.model_dump() if isinstance(payload, RendaFixaProdutoIn) else RendaFixaProdutoIn(**payload).model_dump()
    if data.get("coletado_em") is None:
        data["coletado_em"] = datetime.now(timezone.utc)
    query = select(RendaFixaProduto).where(
        RendaFixaProduto.nome == data["nome"],
        RendaFixaProduto.emissor == data.get("emissor"),
        RendaFixaProduto.tipo == data["tipo"],
        RendaFixaProduto.vencimento == data.get("vencimento"),
        RendaFixaProduto.source == data["source"],
    )
    existing = (await session.execute(query)).scalar_one_or_none()
    if existing is None:
        produto = RendaFixaProduto(**data)
        session.add(produto)
    else:
        for field, value in data.items():
            setattr(existing, field, value)
        produto = existing
    await session.commit()
    await session.refresh(produto)
    return produto


async def list_macro_indicators(session: AsyncSession, *, code: str | None = None) -> tuple[list[MacroIndicator], int]:
    filters = []
    if code:
        filters.append(MacroIndicator.code == code.strip().upper())
    query = select(MacroIndicator).where(*filters).order_by(MacroIndicator.date.desc(), MacroIndicator.code.asc())
    count = select(func.count()).select_from(MacroIndicator).where(*filters)
    total = int((await session.execute(count)).scalar_one() or 0)
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def list_asset_prices(
    session: AsyncSession,
    *,
    market: str,
    ticker: str,
    limit: int = 365,
    offset: int = 0,
) -> tuple[list[AssetPrice], int]:
    filters = [AssetPrice.market == normalize_market(market), AssetPrice.ticker == normalize_ticker(ticker)]
    count = select(func.count()).select_from(AssetPrice).where(*filters)
    total = int((await session.execute(count)).scalar_one() or 0)
    query = select(AssetPrice).where(*filters).order_by(AssetPrice.date.desc()).limit(limit).offset(offset)
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def list_renda_fixa_produtos(session: AsyncSession, *, is_active: bool = True) -> tuple[list[RendaFixaProduto], int]:
    filters = [RendaFixaProduto.is_active.is_(is_active)]
    count = select(func.count()).select_from(RendaFixaProduto).where(*filters)
    total = int((await session.execute(count)).scalar_one() or 0)
    query = select(RendaFixaProduto).where(*filters).order_by(RendaFixaProduto.coletado_em.desc())
    items = list((await session.execute(query)).scalars().all())
    return items, total

from backend.app.market.models import AcaoFundamental, BdrFundamental, CriptoFundamental, EtfFundamental, FiiFundamental

FUNDAMENTALS_MAX_BATCH_SIZE = 500


def _normalize_source(value: str) -> str:
    source = value.strip().lower()
    if not source:
        raise ValueError("source is required")
    return source


def _normalize_coin_id(value: str) -> str:
    coin_id = value.strip().lower()
    if not coin_id:
        raise ValueError("coin_id is required")
    return coin_id


def _ensure_batch_limit(records: list[dict]) -> None:
    if len(records) > FUNDAMENTALS_MAX_BATCH_SIZE:
        raise ValueError("fundamentals batch size must be <= 500")


def _base_filters(model, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None):
    filters = []
    if ticker:
        filters.append(model.ticker == normalize_ticker(ticker))
    if date_from:
        filters.append(model.date >= date_from)
    if date_to:
        filters.append(model.date <= date_to)
    if source:
        filters.append(model.source == _normalize_source(source))
    return filters


async def _list_fundamentals(session: AsyncSession, model, *, ticker=None, date_from=None, date_to=None, source=None, limit=100, offset=0):
    filters = _base_filters(model, ticker=ticker, date_from=date_from, date_to=date_to, source=source)
    total = int((await session.execute(select(func.count()).select_from(model).where(*filters))).scalar_one() or 0)
    query = select(model).where(*filters).order_by(model.date.desc()).limit(limit).offset(offset)
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def list_fii_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, FiiFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


async def list_acoes_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, AcaoFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


async def list_etf_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, EtfFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


async def list_bdr_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, BdrFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


async def list_cripto_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, CriptoFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, limit=limit, offset=offset)


async def _upsert_by_ticker_date_source(session: AsyncSession, model, payload: dict):
    data = dict(payload)
    data["ticker"] = normalize_ticker(data["ticker"])
    data["source"] = _normalize_source(data["source"])
    query = select(model).where(model.ticker == data["ticker"], model.date == data["date"], model.source == data["source"])
    existing = (await session.execute(query)).scalar_one_or_none()
    if existing is None:
        item = model(**data)
        session.add(item)
    else:
        for field, value in data.items():
            setattr(existing, field, value)
        item = existing
    await session.commit()
    await session.refresh(item)
    return item


async def upsert_fii_fundamental(session: AsyncSession, payload: dict):
    return await _upsert_by_ticker_date_source(session, FiiFundamental, payload)


async def upsert_acao_fundamental(session: AsyncSession, payload: dict):
    return await _upsert_by_ticker_date_source(session, AcaoFundamental, payload)


async def upsert_etf_fundamental(session: AsyncSession, payload: dict):
    return await _upsert_by_ticker_date_source(session, EtfFundamental, payload)


async def upsert_bdr_fundamental(session: AsyncSession, payload: dict):
    return await _upsert_by_ticker_date_source(session, BdrFundamental, payload)


async def upsert_cripto_fundamental(session: AsyncSession, payload: dict):
    """Append an intraday crypto snapshot.

    The function name is kept for existing callers, but crypto must not be
    de-duplicated by coin_id/date because the CoinGecko scheduler runs every
    10 minutes and each run is a new historical sample.
    """
    data = dict(payload)
    data["coin_id"] = _normalize_coin_id(data["coin_id"])
    data["ticker"] = normalize_ticker(data["ticker"])
    data["source"] = _normalize_source(data["source"])
    item = CriptoFundamental(**data)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item
