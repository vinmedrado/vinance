from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.logging import get_logger
from backend.app.intelligence.feature_pipeline.common import (
    calculate_anomaly_score,
    calculate_momentum,
    calculate_relative_return,
    calculate_trend,
    calculate_volatility,
    calculate_zscore,
    to_decimal,
)
from backend.app.intelligence.feature_scoring import (
    score_acoes_features,
    score_bdr_features,
    score_cripto_features,
    score_etf_features,
    score_fii_features,
)
from backend.app.intelligence.models import AcaoMLFeature, BdrMLFeature, CriptoMLFeature, EtfMLFeature, FiiMLFeature
from backend.app.market.models import AcaoFundamental, AssetPrice, BdrFundamental, CriptoFundamental, EtfFundamental, FiiFundamental

logger = get_logger(__name__)
FEATURE_BATCH_SIZE = 300


def _chunk(items: Sequence[str], size: int = FEATURE_BATCH_SIZE):
    for index in range(0, len(items), size):
        yield items[index : index + size]


async def _tickers_for_market(session: AsyncSession, market: str, *, limit: int | None = None) -> list[str]:
    stmt = select(AssetPrice.ticker).where(AssetPrice.market == market).distinct().order_by(AssetPrice.ticker.asc())
    if limit:
        stmt = stmt.limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [str(row).upper() for row in rows]


async def _coin_ids(session: AsyncSession, *, limit: int | None = None) -> list[str]:
    stmt = select(CriptoFundamental.coin_id).distinct().order_by(CriptoFundamental.coin_id.asc())
    if limit:
        stmt = stmt.limit(limit)
    return [str(row).lower() for row in (await session.execute(stmt)).scalars().all()]


async def _prices(session: AsyncSession, *, ticker: str, market: str, limit: int = 300) -> list[AssetPrice]:
    stmt = (
        select(AssetPrice)
        .where(AssetPrice.ticker == ticker.upper(), AssetPrice.market == market)
        .order_by(AssetPrice.date.desc())
        .limit(limit)
    )
    return list(reversed((await session.execute(stmt)).scalars().all()))


async def _latest_fundamental(session: AsyncSession, model, *, ticker: str | None = None, coin_id: str | None = None):
    filters = []
    if ticker:
        filters.append(model.ticker == ticker.upper())
    if coin_id:
        filters.append(model.coin_id == coin_id.lower())
    stmt = select(model).where(*filters).order_by(model.date.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _fundamental_values(session: AsyncSession, model, field: str) -> list[Any]:
    column = getattr(model, field)
    stmt = select(column).where(column.is_not(None)).order_by(model.date.desc()).limit(500)
    return list((await session.execute(stmt)).scalars().all())


async def _upsert_feature(session: AsyncSession, model, payload: dict[str, Any], *, coin: bool = False) -> bool:
    data = dict(payload)
    data["calculado_em"] = datetime.now(timezone.utc)
    if coin:
        stmt = select(model).where(model.coin_id == data["coin_id"], model.date == data["date"])
    else:
        data["ticker"] = data["ticker"].upper()
        stmt = select(model).where(model.ticker == data["ticker"], model.date == data["date"])
    existing = (await session.execute(stmt)).scalar_one_or_none()
    inserted = existing is None
    item = model(**data) if inserted else existing
    if inserted:
        session.add(item)
    else:
        for field, value in data.items():
            setattr(item, field, value)
    return inserted


def _close_values(rows: Sequence[AssetPrice]) -> list[Decimal]:
    return [row.close for row in rows if row.close is not None]


def _volume_values(rows: Sequence[AssetPrice]) -> list[Decimal]:
    return [row.volume for row in rows if row.volume is not None]


async def compute_fii_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, int]:
    tickers = await _tickers_for_market(session, "fii", limit=limit_assets)
    pvp_peers = await _fundamental_values(session, FiiFundamental, "pvp")
    processed = inserted = updated = 0
    for batch in _chunk(tickers):
        for ticker in batch:
            prices = await _prices(session, ticker=ticker, market="fii")
            if not prices:
                continue
            close = _close_values(prices)
            latest = await _latest_fundamental(session, FiiFundamental, ticker=ticker)
            dy_trend_3m = None
            pvp_zscore = None
            vacancia_delta = None
            if latest:
                historical_dy = [latest.dy_12m] if latest.dy_12m is not None else []
                dy_trend_3m = calculate_trend(historical_dy, 3)
                pvp_zscore = calculate_zscore(latest.pvp, pvp_peers)
                vacancia_delta = to_decimal(latest.vacancia_fisica) if latest.vacancia_fisica is not None else None
            payload = {
                "ticker": ticker,
                "date": prices[-1].date,
                "dy_trend_3m": dy_trend_3m,
                "pvp_zscore": pvp_zscore,
                "vacancia_delta": vacancia_delta,
                "momentum_30d": calculate_momentum(close, 30),
                "momentum_90d": calculate_momentum(close, 90),
                "volatilidade_30d": calculate_volatility(close, 30),
                "retorno_vs_ifix": None,
            }
            payload["score_final"] = score_fii_features(**{k: payload[k] for k in payload if k not in {"ticker", "date"}})
            was_inserted = await _upsert_feature(session, FiiMLFeature, payload)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            processed += 1
        await session.commit()
    return {"market": "fii", "processed": processed, "inserted": inserted, "updated": updated}


async def compute_acoes_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, int]:
    tickers = await _tickers_for_market(session, "acoes", limit=limit_assets)
    pl_peers = await _fundamental_values(session, AcaoFundamental, "pl")
    processed = inserted = updated = 0
    for batch in _chunk(tickers):
        for ticker in batch:
            prices = await _prices(session, ticker=ticker, market="acoes")
            if not prices:
                continue
            close = _close_values(prices)
            volumes = _volume_values(prices)
            latest = await _latest_fundamental(session, AcaoFundamental, ticker=ticker)
            payload = {
                "ticker": ticker,
                "date": prices[-1].date,
                "pl_zscore": calculate_zscore(getattr(latest, "pl", None), pl_peers) if latest else None,
                "roe_trend_3m": calculate_trend([latest.roe] if latest and latest.roe is not None else [], 3),
                "momentum_30d": calculate_momentum(close, 30),
                "momentum_90d": calculate_momentum(close, 90),
                "momentum_252d": calculate_momentum(close, 252),
                "volatilidade_30d": calculate_volatility(close, 30),
                "volatilidade_90d": calculate_volatility(close, 90),
                "retorno_vs_ibov": None,
                "volume_anomaly": calculate_anomaly_score(volumes[-1], volumes[-90:]) if volumes else None,
            }
            payload["score_final"] = score_acoes_features(**{k: payload[k] for k in payload if k not in {"ticker", "date"}})
            was_inserted = await _upsert_feature(session, AcaoMLFeature, payload)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            processed += 1
        await session.commit()
    return {"market": "acoes", "processed": processed, "inserted": inserted, "updated": updated}


async def compute_etf_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, int]:
    tickers = await _tickers_for_market(session, "etf", limit=limit_assets)
    processed = inserted = updated = 0
    for batch in _chunk(tickers):
        for ticker in batch:
            prices = await _prices(session, ticker=ticker, market="etf")
            if not prices:
                continue
            close = _close_values(prices)
            latest = await _latest_fundamental(session, EtfFundamental, ticker=ticker)
            taxa_adm_rank = None if latest is None or latest.taxa_adm is None else max(Decimal("0"), Decimal("100") - Decimal(str(latest.taxa_adm)))
            tracking_score = None if latest is None or latest.tracking_error is None else max(Decimal("0"), Decimal("100") - Decimal(str(latest.tracking_error)))
            payload = {
                "ticker": ticker,
                "date": prices[-1].date,
                "taxa_adm_rank": taxa_adm_rank,
                "tracking_score": tracking_score,
                "momentum_30d": calculate_momentum(close, 30),
                "momentum_90d": calculate_momentum(close, 90),
                "volatilidade_30d": calculate_volatility(close, 30),
                "retorno_vs_benchmark": None,
            }
            payload["score_final"] = score_etf_features(**{k: payload[k] for k in payload if k not in {"ticker", "date"}})
            was_inserted = await _upsert_feature(session, EtfMLFeature, payload)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            processed += 1
        await session.commit()
    return {"market": "etf", "processed": processed, "inserted": inserted, "updated": updated}


async def compute_bdr_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, int]:
    tickers = await _tickers_for_market(session, "bdr", limit=limit_assets)
    processed = inserted = updated = 0
    for batch in _chunk(tickers):
        for ticker in batch:
            prices = await _prices(session, ticker=ticker, market="bdr")
            if not prices:
                continue
            close = _close_values(prices)
            latest = await _latest_fundamental(session, BdrFundamental, ticker=ticker)
            liquidity = getattr(latest, "volume_medio_diario_brl", None) if latest else None
            payload = {
                "ticker": ticker,
                "date": prices[-1].date,
                "cambio_trend_30d": None,
                "momentum_30d": calculate_momentum(close, 30),
                "momentum_90d": calculate_momentum(close, 90),
                "volatilidade_30d": calculate_volatility(close, 30),
                "retorno_vs_spy": None,
                "liquidez_score": calculate_anomaly_score(liquidity, [liquidity]) if liquidity else None,
            }
            payload["score_final"] = score_bdr_features(**{k: payload[k] for k in payload if k not in {"ticker", "date"}})
            was_inserted = await _upsert_feature(session, BdrMLFeature, payload)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            processed += 1
        await session.commit()
    return {"market": "bdr", "processed": processed, "inserted": inserted, "updated": updated}


async def compute_cripto_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, int]:
    coin_ids = await _coin_ids(session, limit=limit_assets)
    processed = inserted = updated = 0
    for batch in _chunk(coin_ids):
        for coin_id in batch:
            fundamentals_stmt = (
                select(CriptoFundamental)
                .where(CriptoFundamental.coin_id == coin_id)
                .order_by(CriptoFundamental.date.desc())
                .limit(120)
            )
            fundamentals = list(reversed((await session.execute(fundamentals_stmt)).scalars().all()))
            if not fundamentals:
                continue
            prices = [row.price_usd for row in fundamentals if row.price_usd is not None]
            volumes = [row.volume_24h_usd for row in fundamentals if row.volume_24h_usd is not None]
            latest = fundamentals[-1]
            btc_prices = prices if coin_id == "bitcoin" else []
            payload = {
                "coin_id": coin_id,
                "ticker": latest.ticker.upper(),
                "date": latest.date,
                "volatilidade_7d": calculate_volatility(prices, 7),
                "volatilidade_30d": calculate_volatility(prices, 30),
                "correlacao_btc_30d": Decimal("1.000000") if coin_id == "bitcoin" else None,
                "momentum_7d": calculate_momentum(prices, 7),
                "momentum_30d": calculate_momentum(prices, 30),
                "momentum_90d": calculate_momentum(prices, 90),
                "volume_anomaly": calculate_anomaly_score(volumes[-1], volumes[-90:]) if volumes else None,
                "fear_greed_score": None,
            }
            payload["score_final"] = score_cripto_features(**{k: payload[k] for k in payload if k not in {"coin_id", "ticker", "date"}})
            was_inserted = await _upsert_feature(session, CriptoMLFeature, payload, coin=True)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
            processed += 1
        await session.commit()
    return {"market": "cripto", "processed": processed, "inserted": inserted, "updated": updated}


async def compute_all_features(session: AsyncSession, *, limit_assets: int | None = None) -> dict[str, Any]:
    results = []
    for fn in (compute_fii_features, compute_acoes_features, compute_etf_features, compute_bdr_features, compute_cripto_features):
        try:
            results.append(await fn(session, limit_assets=limit_assets))
        except Exception as exc:  # noqa: BLE001 - feature pipeline must be batch-resilient
            logger.exception("Feature pipeline market failed", extra={"function": fn.__name__, "error": str(exc)})
            results.append({"market": fn.__name__.replace("compute_", "").replace("_features", ""), "processed": 0, "error": str(exc)})
    return {"markets": results, "processed": sum(int(item.get("processed", 0)) for item in results)}


_FEATURE_MODELS = {
    "fii": FiiMLFeature,
    "acoes": AcaoMLFeature,
    "etf": EtfMLFeature,
    "bdr": BdrMLFeature,
    "cripto": CriptoMLFeature,
}


async def get_features_status(session: AsyncSession) -> dict[str, Any]:
    markets: dict[str, Any] = {}
    for market, model in _FEATURE_MODELS.items():
        count = int((await session.execute(select(func.count()).select_from(model))).scalar_one() or 0)
        latest = (await session.execute(select(func.max(model.date)))).scalar_one_or_none()
        markets[market] = {"count": count, "latest_date": latest.isoformat() if latest else None}
    status = "ready" if any(item["count"] for item in markets.values()) else "empty"
    return {"status": status, "markets": markets}


async def latest_feature_scores(session: AsyncSession, *, asset_class: str, limit: int = 100) -> dict[str, Decimal]:
    model = _FEATURE_MODELS.get(asset_class)
    if model is None:
        return {}
    latest_date = (await session.execute(select(func.max(model.date)))).scalar_one_or_none()
    if latest_date is None:
        return {}
    stmt = select(model).where(model.date == latest_date, model.score_final.is_not(None)).order_by(model.score_final.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    if asset_class == "cripto":
        return {row.ticker.upper(): row.score_final for row in rows if row.score_final is not None}
    return {row.ticker.upper(): row.score_final for row in rows if row.score_final is not None}
