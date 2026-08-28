from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.asset_trend_signal_model import AssetTrendSignal
from backend.app.intelligence.services.asset_score_service import MARKET_MODELS, normalize_market

TREND_SOURCE = "vinance_trend_v1"
UPTREND = "UPTREND"
SIDEWAYS = "SIDEWAYS"
DOWNTREND = "DOWNTREND"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
UNKNOWN = "UNKNOWN"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_VERY_LOW = "VERY_LOW"
METHOD_30D = "ADAPTIVE_30D"
METHOD_7D = "ADAPTIVE_7D"
METHOD_SHORT = "ADAPTIVE_SHORT"
METHOD_INSUFFICIENT = "INSUFFICIENT_HISTORY"
VALID_TRENDS = {UPTREND, SIDEWAYS, DOWNTREND, INSUFFICIENT_HISTORY}
MARKETS = ("FII", "ACOES", "ETF", "BDR")


@dataclass(frozen=True)
class PricePoint:
    ticker: str
    date: date
    price: Decimal | None


def normalize_trend_label(trend: str | None) -> str | None:
    if trend is None or str(trend).strip() == "":
        return None
    normalized = str(trend).strip().upper()
    if normalized not in VALID_TRENDS:
        raise ValueError(f"Trend inválido: {trend}")
    return normalized


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None
    return number if number > 0 else None


def _round_decimal(value: float | Decimal | None, scale: str = "0.0001") -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal(scale), rounding=ROUND_HALF_UP)


def _return_pct(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None or previous <= 0:
        return None
    return _round_decimal(((current - previous) / previous) * Decimal("100"), "0.000001")


def _decimal_to_metadata(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _price_at_or_before(points: list[PricePoint], target: date) -> Decimal | None:
    candidates = [point for point in points if point.date <= target and _to_decimal(point.price) is not None]
    if not candidates:
        return None
    return _to_decimal(candidates[-1].price)


def _return_for_horizon(points: list[PricePoint], current_price: Decimal | None, latest_date: date, horizon_days: int) -> Decimal | None:
    date_based_price = _price_at_or_before(points, latest_date - timedelta(days=horizon_days))
    if date_based_price is not None:
        return _return_pct(current_price, date_based_price)
    clean = [point for point in points if _to_decimal(point.price) is not None]
    if len(clean) > horizon_days:
        return _return_pct(current_price, _to_decimal(clean[-(horizon_days + 1)].price))
    if horizon_days == 7 and len(clean) >= 7:
        return _return_pct(current_price, _to_decimal(clean[0].price))
    if horizon_days == 30 and len(clean) >= 30:
        return _return_pct(current_price, _to_decimal(clean[0].price))
    return None


def _daily_returns(points: list[PricePoint], max_records: int = 30) -> list[float]:
    clean = [point for point in points if _to_decimal(point.price) is not None]
    if len(clean) < 3:
        return []
    tail = clean[-(max_records + 1) :]
    returns: list[float] = []
    for previous, current in zip(tail, tail[1:]):
        previous_price = _to_decimal(previous.price)
        current_price = _to_decimal(current.price)
        pct = _return_pct(current_price, previous_price)
        if pct is not None:
            returns.append(float(pct))
    return returns


def _volatility_30d(points: list[PricePoint]) -> Decimal | None:
    returns = _daily_returns(points, 30)
    if len(returns) < 2:
        return None
    return _round_decimal(statistics.stdev(returns), "0.000001")


def _short_volatility(points: list[PricePoint]) -> Decimal | None:
    returns = _daily_returns(points, max_records=min(7, max(1, len(points) - 1)))
    if len(returns) < 2:
        return None
    return _round_decimal(statistics.stdev(returns), "0.000001")


def _confidence_level(history_count: int) -> str:
    if history_count >= 30:
        return CONFIDENCE_HIGH
    if history_count >= 7:
        return CONFIDENCE_MEDIUM
    if history_count >= 3:
        return CONFIDENCE_LOW
    return CONFIDENCE_VERY_LOW


def _trend_method(history_count: int) -> str:
    if history_count >= 30:
        return METHOD_30D
    if history_count >= 7:
        return METHOD_7D
    if history_count >= 3:
        return METHOD_SHORT
    return METHOD_INSUFFICIENT


def _short_cumulative_return(points: list[PricePoint]) -> Decimal | None:
    clean = [point for point in points if _to_decimal(point.price) is not None]
    if len(clean) < 3:
        return None
    return _return_pct(_to_decimal(clean[-1].price), _to_decimal(clean[0].price))


def _direction_consistency(points: list[PricePoint]) -> Decimal | None:
    returns = _daily_returns(points, max_records=max(1, len(points) - 1))
    if not returns:
        return None
    positive = sum(1 for item in returns if item > 0)
    negative = sum(1 for item in returns if item < 0)
    total = len(returns)
    if total == 0:
        return None
    if positive >= negative:
        return _round_decimal(Decimal(positive) / Decimal(total), "0.0001")
    return _round_decimal(Decimal(negative) / Decimal(total), "0.0001")


def _adaptive_trend_label(
    *,
    history_count: int,
    return_1d: Decimal | None,
    return_7d: Decimal | None,
    return_30d: Decimal | None,
    short_return: Decimal | None,
    direction_consistency: Decimal | None,
) -> str:
    if history_count < 3:
        return INSUFFICIENT_HISTORY
    if history_count >= 30:
        if return_7d is not None and return_30d is not None:
            if return_7d > 0 and return_30d > 0:
                return UPTREND
            if return_7d < 0 and return_30d < 0:
                return DOWNTREND
        return SIDEWAYS
    if history_count >= 7:
        if return_1d is not None and return_7d is not None:
            if return_1d > 0 and return_7d > 0:
                return UPTREND
            if return_1d < 0 and return_7d < 0:
                return DOWNTREND
        return SIDEWAYS
    if short_return is None:
        return SIDEWAYS
    consistency = direction_consistency or Decimal("0")
    if short_return > 0 and consistency >= Decimal("0.50"):
        return UPTREND
    if short_return < 0 and consistency >= Decimal("0.50"):
        return DOWNTREND
    return SIDEWAYS


def _risk_label(volatility_30d: Decimal | None) -> str:
    if volatility_30d is None:
        return UNKNOWN
    if volatility_30d <= Decimal("1.5"):
        return LOW
    if volatility_30d <= Decimal("3.5"):
        return MEDIUM
    return HIGH


def _adaptive_momentum_score(
    *,
    return_1d: Decimal | None,
    return_7d: Decimal | None,
    return_30d: Decimal | None,
    return_90d: Decimal | None,
    volatility_30d: Decimal | None,
    short_volatility: Decimal | None,
    short_return: Decimal | None,
    direction_consistency: Decimal | None,
    history_count: int,
) -> Decimal:
    score = 50.0
    available = 0
    if history_count >= 30:
        factors = ((return_7d, 0.8), (return_30d, 0.6), (return_90d, 0.3))
        volatility = volatility_30d
        coverage = 1.0
    elif history_count >= 7:
        factors = ((return_1d, 0.6), (return_7d, 0.9))
        volatility = short_volatility or volatility_30d
        coverage = 0.85
    elif history_count >= 3:
        factors = ((short_return, 1.0),)
        volatility = short_volatility
        coverage = 0.70
        if direction_consistency is not None:
            score += (float(direction_consistency) - 0.5) * 20.0
    else:
        factors = ()
        volatility = None
        coverage = 0.55

    for value, weight in factors:
        if value is None:
            continue
        available += 1
        score += max(-18.0, min(18.0, float(value) * weight))
    if volatility is not None:
        score -= min(25.0, float(volatility) * 3.0)
    score *= coverage
    if available == 0:
        score = min(score, 35.0)
    return Decimal(str(max(0.0, min(100.0, score)))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_trend_for_points(points: list[PricePoint], market: str, *, source: str = TREND_SOURCE) -> dict[str, Any] | None:
    if not points:
        return None
    points = sorted(points, key=lambda item: item.date)
    latest = points[-1]
    current_price = _to_decimal(latest.price)
    previous_price = _to_decimal(points[-2].price) if len(points) >= 2 else None
    returns = {
        "return_1d": _return_pct(current_price, previous_price),
        "return_7d": _return_for_horizon(points, current_price, latest.date, 7),
        "return_30d": _return_for_horizon(points, current_price, latest.date, 30),
        "return_90d": _return_for_horizon(points, current_price, latest.date, 90),
        "return_180d": _return_for_horizon(points, current_price, latest.date, 180),
        "return_365d": _return_for_horizon(points, current_price, latest.date, 365),
    }
    observations_count = len([point for point in points if _to_decimal(point.price) is not None])
    volatility = _volatility_30d(points)
    short_volatility = _short_volatility(points)
    short_return = _short_cumulative_return(points)
    direction_consistency = _direction_consistency(points)
    confidence_level = _confidence_level(observations_count)
    trend_method = _trend_method(observations_count)
    trend = _adaptive_trend_label(
        history_count=observations_count,
        return_1d=returns["return_1d"],
        return_7d=returns["return_7d"],
        return_30d=returns["return_30d"],
        short_return=short_return,
        direction_consistency=direction_consistency,
    )
    risk = _risk_label(volatility or short_volatility)
    momentum = _adaptive_momentum_score(
        return_1d=returns["return_1d"],
        return_7d=returns["return_7d"],
        return_30d=returns["return_30d"],
        return_90d=returns["return_90d"],
        volatility_30d=volatility,
        short_volatility=short_volatility,
        short_return=short_return,
        direction_consistency=direction_consistency,
        history_count=observations_count,
    )
    return {
        "ticker": latest.ticker.upper(),
        "market": normalize_market(market),
        "date": latest.date,
        "price": current_price,
        **returns,
        "volatility_30d": volatility,
        "momentum_score": momentum,
        "trend_label": trend,
        "risk_label": risk,
        "metadata_json": {
            "version": source,
            "history_points": len(points),
            "observations_count": observations_count,
            "trend_method": trend_method,
            "confidence_level": confidence_level,
            "short_return": _decimal_to_metadata(short_return),
            "short_volatility": _decimal_to_metadata(short_volatility),
            "direction_consistency": _decimal_to_metadata(direction_consistency),
            "methodology": "adaptive trend: >=30 observations uses 7d/30d; >=7 uses 1d/7d; >=3 uses short cumulative return and direction consistency; volatility uses available daily returns",
        },
        "source": source,
    }


def calculate_trends_for_rows(rows: list[Any], market: str, *, source: str = TREND_SOURCE) -> list[dict[str, Any]]:
    grouped: dict[str, list[PricePoint]] = {}
    for row in rows:
        ticker = str(getattr(row, "ticker", "")).upper().strip()
        row_date = getattr(row, "date", None)
        if not ticker or row_date is None:
            continue
        grouped.setdefault(ticker, []).append(PricePoint(ticker=ticker, date=row_date, price=getattr(row, "price", None)))
    payloads: list[dict[str, Any]] = []
    for points in grouped.values():
        payload = calculate_trend_for_points(points, market, source=source)
        if payload is not None:
            payloads.append(payload)
    return payloads


async def list_price_history(session: AsyncSession, market: str) -> list[Any]:
    model = MARKET_MODELS[normalize_market(market)]
    result = await session.execute(select(model).where(model.price.is_not(None)).order_by(model.ticker.asc(), model.date.asc()))
    return list(result.scalars().all())


async def upsert_trend_signals(session: AsyncSession, payloads: Iterable[dict[str, Any]]) -> int:
    rows = list(payloads)
    if not rows:
        return 0
    stmt = pg_insert(AssetTrendSignal).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_trend_signals_ticker_market_date_source",
        set_={
            "price": excluded.price,
            "return_1d": excluded.return_1d,
            "return_7d": excluded.return_7d,
            "return_30d": excluded.return_30d,
            "return_90d": excluded.return_90d,
            "return_180d": excluded.return_180d,
            "return_365d": excluded.return_365d,
            "volatility_30d": excluded.volatility_30d,
            "momentum_score": excluded.momentum_score,
            "trend_label": excluded.trend_label,
            "risk_label": excluded.risk_label,
            "metadata_json": excluded.metadata_json,
            "calculated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def calculate_market_trend_signals(session: AsyncSession, market: str, *, source: str = TREND_SOURCE) -> dict[str, Any]:
    normalized_market = normalize_market(market)
    rows = await list_price_history(session, normalized_market)
    payloads = calculate_trends_for_rows(rows, normalized_market, source=source)
    saved = await upsert_trend_signals(session, payloads)
    return {"market": normalized_market, "status": "SUCCESS", "source": source, "saved": saved}


async def calculate_all_trend_signals(session: AsyncSession, *, source: str = TREND_SOURCE) -> dict[str, Any]:
    results = [await calculate_market_trend_signals(session, market, source=source) for market in MARKETS]
    return {"status": "SUCCESS", "source": source, "saved": sum(int(item.get("saved") or 0) for item in results), "results": results}


async def latest_trend_date(session: AsyncSession, market: str) -> date | None:
    result = await session.execute(
        select(func.max(AssetTrendSignal.date)).where(AssetTrendSignal.market == normalize_market(market), AssetTrendSignal.source == TREND_SOURCE)
    )
    return result.scalar_one_or_none()


async def list_trends(session: AsyncSession, *, market: str, trend: str | None = None, limit: int = 50) -> list[AssetTrendSignal]:
    normalized_market = normalize_market(market)
    normalized_trend = normalize_trend_label(trend)
    target_date = await latest_trend_date(session, normalized_market)
    if target_date is None:
        return []
    stmt = select(AssetTrendSignal).where(
        AssetTrendSignal.market == normalized_market,
        AssetTrendSignal.date == target_date,
        AssetTrendSignal.source == TREND_SOURCE,
    )
    if normalized_trend is not None:
        stmt = stmt.where(AssetTrendSignal.trend_label == normalized_trend)
    stmt = stmt.order_by(AssetTrendSignal.momentum_score.desc(), AssetTrendSignal.ticker.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def ticker_set_for_trend(session: AsyncSession, *, market: str, trend: str) -> set[str]:
    rows = await list_trends(session, market=market, trend=trend, limit=10000)
    return {row.ticker.upper() for row in rows}
