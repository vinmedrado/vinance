from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
from typing import Iterable

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.market.models import AssetPrice, MacroIndicator, RendaFixaProduto
from backend.app.catalog.models import AssetCatalog
from backend.app.market.schemas import AssetPriceIn, MacroIndicatorIn, RendaFixaProdutoIn, normalize_market, normalize_ticker

MAX_BULK_BATCH_SIZE = 500
# A source snapshot that suddenly loses more than one quarter of the currently
# active universe is treated as incomplete. This fail-closed ingestion guard is
# about provider integrity, not investment suitability.
FIXED_INCOME_MIN_SNAPSHOT_RETENTION_NUMERATOR = 3
FIXED_INCOME_MIN_SNAPSHOT_RETENTION_DENOMINATOR = 4
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
        RendaFixaProduto.source == data["source"],
        RendaFixaProduto.source_product_id == data["source_product_id"],
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


def fixed_income_catalog_ticker(source: str, source_product_id: str) -> str:
    """Create a stable catalog surrogate without using a display name."""

    digest = hashlib.sha256(
        f"{source.strip().lower()}:{source_product_id.strip()}".encode("utf-8")
    ).hexdigest()[:20]
    return f"TD-{digest}".upper()


async def sync_renda_fixa_produtos(
    session: AsyncSession,
    *,
    produtos: list[RendaFixaProdutoIn | dict],
    source: str,
) -> dict[str, int]:
    """Atomically persist one successful, non-empty provider snapshot."""

    normalized_source = source.strip().lower()
    if not normalized_source:
        raise ValueError("source is required")
    if not produtos:
        raise ValueError("a successful fixed-income snapshot cannot be empty")

    payloads: list[dict] = []
    identities: set[str] = set()
    for raw in produtos:
        data = (
            raw.model_dump()
            if isinstance(raw, RendaFixaProdutoIn)
            else RendaFixaProdutoIn(**raw).model_dump()
        )
        if data["source"].strip().lower() != normalized_source:
            raise ValueError("all fixed-income products must belong to the same source")
        identity = data["source_product_id"]
        if identity in identities:
            raise ValueError(f"duplicate source product identity: {identity}")
        identities.add(identity)
        data["source"] = normalized_source
        if data.get("coletado_em") is None:
            data["coletado_em"] = datetime.now(timezone.utc)
        payloads.append(data)

    existing_result = await session.execute(
        select(RendaFixaProduto).where(RendaFixaProduto.source == normalized_source)
    )
    existing_by_identity = {
        item.source_product_id: item for item in existing_result.scalars().all()
    }
    active_existing_count = sum(
        1 for item in existing_by_identity.values() if item.is_active
    )
    if (
        active_existing_count
        and len(payloads) * FIXED_INCOME_MIN_SNAPSHOT_RETENTION_DENOMINATOR
        < active_existing_count * FIXED_INCOME_MIN_SNAPSHOT_RETENTION_NUMERATOR
    ):
        raise ValueError(
            "fixed-income snapshot is unexpectedly smaller than the active universe"
        )

    catalog_tickers = {
        fixed_income_catalog_ticker(normalized_source, identity): identity
        for identity in identities
    }
    catalog_result = await session.execute(
        select(AssetCatalog).where(
            AssetCatalog.market == "renda_fixa",
            AssetCatalog.ticker.in_(list(catalog_tickers)),
        )
    )
    catalog_by_ticker = {
        str(item.ticker).upper(): item for item in catalog_result.scalars().all()
    }
    existing_catalog_ids = {
        int(item.asset_catalog_id)
        for item in existing_by_identity.values()
        if item.asset_catalog_id is not None
    }
    catalog_by_id: dict[int, AssetCatalog] = {}
    if existing_catalog_ids:
        existing_catalog_result = await session.execute(
            select(AssetCatalog).where(AssetCatalog.id.in_(existing_catalog_ids))
        )
        catalog_by_id = {
            int(item.id): item for item in existing_catalog_result.scalars().all()
        }

    inserted = 0
    updated = 0
    for data in payloads:
        ticker = fixed_income_catalog_ticker(
            normalized_source, data["source_product_id"]
        )
        catalog = catalog_by_ticker.get(ticker)
        if catalog is None:
            catalog = AssetCatalog(
                ticker=ticker,
                name=data["nome"],
                market="renda_fixa",
                sector="RENDA_FIXA",
                segment=data["tipo"],
                currency=data["currency"],
                exchange="TESOURO_DIRETO",
                source=normalized_source,
                is_active=True,
            )
            session.add(catalog)
            await session.flush()
            catalog_by_ticker[ticker] = catalog
        else:
            catalog.name = data["nome"]
            catalog.segment = data["tipo"]
            catalog.currency = data["currency"]
            catalog.source = normalized_source
            catalog.is_active = True

        data["asset_catalog_id"] = catalog.id
        existing = existing_by_identity.get(data["source_product_id"])
        if existing is None:
            session.add(RendaFixaProduto(**data))
            inserted += 1
        else:
            for field, value in data.items():
                setattr(existing, field, value)
            updated += 1

    deactivated = 0
    for identity, existing in existing_by_identity.items():
        if identity in identities or not existing.is_active:
            continue
        existing.is_active = False
        if existing.asset_catalog_id is not None:
            catalog = catalog_by_id.get(int(existing.asset_catalog_id))
            if catalog is not None:
                catalog.is_active = False
        deactivated += 1

    await session.commit()
    return {
        "processed": len(payloads),
        "inserted": inserted,
        "updated": updated,
        "deactivated": deactivated,
    }


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


def _fundamentals_search_filter(model, search: str | None):
    term = (search or "").strip()
    if not term:
        return None
    fields = [model.ticker, model.name]
    if model is CriptoFundamental:
        fields.append(model.coin_id)
    return or_(*(field.icontains(term, autoescape=True) for field in fields))


async def _list_fundamentals(
    session: AsyncSession,
    model,
    *,
    ticker=None,
    date_from=None,
    date_to=None,
    source=None,
    search: str | None = None,
    latest: bool = False,
    limit=100,
    offset=0,
):
    if latest:
        # The product view is a current market snapshot, not a page from the
        # historical observation stream. Restricting the ranking to the most
        # recent market date keeps the cost bounded by one provider snapshot
        # (especially important for the multi-million-row crypto history).
        snapshot_filters = _base_filters(
            model,
            date_from=date_from,
            date_to=date_to,
            source=source,
        )
        snapshot_date = (
            select(func.max(model.date))
            .where(*snapshot_filters)
            .scalar_subquery()
        )
        identity = model.coin_id if model is CriptoFundamental else model.ticker
        ranked = (
            select(
                model.id.label("record_id"),
                func.row_number()
                .over(
                    partition_by=identity,
                    order_by=(model.coletado_em.desc(), model.id.desc()),
                )
                .label("snapshot_rank"),
            )
            .where(*snapshot_filters, model.date == snapshot_date)
            .subquery()
        )
        result_filters = [ranked.c.snapshot_rank == 1]
        if ticker:
            result_filters.append(model.ticker == normalize_ticker(ticker))
        search_filter = _fundamentals_search_filter(model, search)
        if search_filter is not None:
            result_filters.append(search_filter)

        current_rows = (
            select(model)
            .join(ranked, ranked.c.record_id == model.id)
            .where(*result_filters)
        )
        total_query = select(func.count()).select_from(current_rows.subquery())
        total = int((await session.execute(total_query)).scalar_one() or 0)
        query = (
            current_rows
            .order_by(model.ticker.asc(), model.name.asc(), model.id.desc())
            .limit(limit)
            .offset(offset)
        )
        items = list((await session.execute(query)).scalars().all())
        return items, total

    filters = _base_filters(model, ticker=ticker, date_from=date_from, date_to=date_to, source=source)
    search_filter = _fundamentals_search_filter(model, search)
    if search_filter is not None:
        filters.append(search_filter)
    total = int((await session.execute(select(func.count()).select_from(model).where(*filters))).scalar_one() or 0)
    query = (
        select(model)
        .where(*filters)
        .order_by(model.date.desc(), model.coletado_em.desc(), model.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.execute(query)).scalars().all())
    return items, total


async def list_fii_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, search: str | None = None, latest: bool = False, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, FiiFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, search=search, latest=latest, limit=limit, offset=offset)


async def list_acoes_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, search: str | None = None, latest: bool = False, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, AcaoFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, search=search, latest=latest, limit=limit, offset=offset)


async def list_etf_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, search: str | None = None, latest: bool = False, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, EtfFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, search=search, latest=latest, limit=limit, offset=offset)


async def list_bdr_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, search: str | None = None, latest: bool = False, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, BdrFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, search=search, latest=latest, limit=limit, offset=offset)


async def list_cripto_fundamentals(session: AsyncSession, *, ticker: str | None = None, date_from: date | None = None, date_to: date | None = None, source: str | None = None, search: str | None = None, latest: bool = False, limit: int = 100, offset: int = 0):
    return await _list_fundamentals(session, CriptoFundamental, ticker=ticker, date_from=date_from, date_to=date_to, source=source, search=search, latest=latest, limit=limit, offset=offset)


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
