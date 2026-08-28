from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.models import AcaoMLFeature, CriptoMLFeature, FiiMLFeature
from backend.app.market.models import AssetPrice

FEATURE_MODEL_BY_MARKET = {
    "acoes": AcaoMLFeature,
    "fii": FiiMLFeature,
    "cripto": CriptoMLFeature,
}

FEATURE_COLUMNS_BY_MARKET = {
    "acoes": [
        "pl_zscore",
        "roe_trend_3m",
        "momentum_30d",
        "momentum_90d",
        "momentum_252d",
        "volatilidade_30d",
        "volatilidade_90d",
        "retorno_vs_ibov",
        "volume_anomaly",
        "score_final",
    ],
    "fii": [
        "dy_trend_3m",
        "pvp_zscore",
        "vacancia_delta",
        "momentum_30d",
        "momentum_90d",
        "volatilidade_30d",
        "retorno_vs_ifix",
        "score_final",
    ],
    "cripto": [
        "volatilidade_7d",
        "volatilidade_30d",
        "correlacao_btc_30d",
        "momentum_7d",
        "momentum_30d",
        "momentum_90d",
        "volume_anomaly",
        "fear_greed_score",
        "score_final",
    ],
}


@dataclass(slots=True)
class SupervisedDataset:
    market: str
    horizon_days: int
    feature_columns: list[str]
    rows: list[dict[str, Any]]
    warnings: list[str]

    @property
    def sample_size(self) -> int:
        return len(self.rows)

    def to_xy(self) -> tuple[list[list[float]], list[float], list[dict[str, Any]]]:
        x_values: list[list[float]] = []
        y_values: list[float] = []
        metadata: list[dict[str, Any]] = []
        for row in self.rows:
            x_values.append([float(row.get(column) or 0.0) for column in self.feature_columns])
            y_values.append(float(row["target_return"]))
            metadata.append({"ticker": row.get("ticker"), "date": row.get("date")})
        return x_values, y_values, metadata


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _price_on_or_after(session: AsyncSession, *, ticker: str, market: str, min_date: date) -> AssetPrice | None:
    result = await session.execute(
        select(AssetPrice)
        .where(
            AssetPrice.ticker == ticker,
            AssetPrice.market == market,
            AssetPrice.date >= min_date,
        )
        .order_by(AssetPrice.date.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_supervised_dataset(
    session: AsyncSession,
    *,
    market: str,
    horizon_days: int = 90,
    min_feature_date: date | None = None,
    max_feature_date: date | None = None,
    limit: int | None = None,
) -> SupervisedDataset:
    if market not in FEATURE_MODEL_BY_MARKET:
        raise ValueError(f"Mercado não suportado para ML baseline: {market}")

    model = FEATURE_MODEL_BY_MARKET[market]
    feature_columns = FEATURE_COLUMNS_BY_MARKET[market]
    query = select(model).order_by(model.date.asc())
    filters = []
    if min_feature_date:
        filters.append(model.date >= min_feature_date)
    if max_feature_date:
        filters.append(model.date <= max_feature_date)
    if filters:
        query = query.where(and_(*filters))
    if limit:
        query = query.limit(limit)

    feature_rows = list((await session.execute(query)).scalars().all())
    warnings: list[str] = []
    dataset_rows: list[dict[str, Any]] = []

    for feature in feature_rows:
        ticker = getattr(feature, "ticker", None)
        if not ticker:
            continue
        start_price = await _price_on_or_after(session, ticker=ticker, market=market, min_date=feature.date)
        future_price = await _price_on_or_after(
            session,
            ticker=ticker,
            market=market,
            min_date=feature.date + timedelta(days=horizon_days),
        )
        if not start_price or not future_price:
            warnings.append(f"{ticker}: ignorado por ausência de preço inicial/futuro para target {horizon_days}d")
            continue
        initial = Decimal(start_price.close)
        final = Decimal(future_price.close)
        if initial <= 0:
            warnings.append(f"{ticker}: ignorado por preço inicial inválido")
            continue
        target_return = float((final / initial) - Decimal("1"))
        row = {
            "ticker": ticker,
            "date": feature.date.isoformat(),
            "target_return": target_return,
            "start_price_date": start_price.date.isoformat(),
            "future_price_date": future_price.date.isoformat(),
        }
        for column in feature_columns:
            row[column] = _to_float(getattr(feature, column, None))
        dataset_rows.append(row)

    return SupervisedDataset(market=market, horizon_days=horizon_days, feature_columns=feature_columns, rows=dataset_rows, warnings=warnings)


async def latest_feature_matrix(session: AsyncSession, *, market: str, limit: int = 100) -> tuple[list[dict[str, Any]], list[str]]:
    if market not in FEATURE_MODEL_BY_MARKET:
        raise ValueError(f"Mercado não suportado para ML baseline: {market}")
    model = FEATURE_MODEL_BY_MARKET[market]
    feature_columns = FEATURE_COLUMNS_BY_MARKET[market]

    subquery = select(model.ticker, model.date).order_by(model.date.desc()).subquery()
    # Simpler and portable approach: fetch recent rows and keep latest per ticker in Python.
    result = await session.execute(select(model).order_by(model.date.desc()).limit(max(limit * 5, limit)))
    rows = list(result.scalars().all())
    seen: set[str] = set()
    matrix: list[dict[str, Any]] = []
    for feature in rows:
        ticker = getattr(feature, "ticker", None)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        row = {"ticker": ticker, "date": feature.date.isoformat()}
        for column in feature_columns:
            row[column] = _to_float(getattr(feature, column, None))
        matrix.append(row)
        if len(matrix) >= limit:
            break
    return matrix, feature_columns
