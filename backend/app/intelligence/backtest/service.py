from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.backtest.engine import FeaturePoint, PricePoint, run_ranking_backtest
from backend.app.intelligence.models.acoes_features import AcaoMLFeature
from backend.app.intelligence.models.bdr_features import BdrMLFeature
from backend.app.intelligence.models.cripto_features import CriptoMLFeature
from backend.app.intelligence.models.etf_features import EtfMLFeature
from backend.app.intelligence.models.fii_features import FiiMLFeature
from backend.app.market.models.prices import AssetPrice

FEATURE_MODELS = {
    "acoes": AcaoMLFeature,
    "fii": FiiMLFeature,
    "etf": EtfMLFeature,
    "bdr": BdrMLFeature,
    "cripto": CriptoMLFeature,
}


async def _load_features(session: AsyncSession, *, market: str, start_date: date, end_date: date) -> list[FeaturePoint]:
    model = FEATURE_MODELS[market]
    stmt = select(model).where(model.date >= start_date, model.date <= end_date).order_by(model.date.asc(), model.score_final.desc())
    result = await session.execute(stmt)
    rows = result.scalars().all()
    points: list[FeaturePoint] = []
    for row in rows:
        ticker = getattr(row, "ticker", None) or getattr(row, "coin_id", None)
        if ticker:
            points.append(FeaturePoint(ticker=str(ticker).upper(), date=row.date, score_final=row.score_final))
    return points


async def _load_prices(session: AsyncSession, *, market: str, start_date: date, end_date: date, holding_period_days: int) -> list[PricePoint]:
    # Busca preço além do end_date para permitir cálculo da janela futura solicitada.
    from datetime import timedelta

    price_end = end_date + timedelta(days=holding_period_days + 10)
    stmt = (
        select(AssetPrice)
        .where(AssetPrice.market == market, AssetPrice.date >= start_date, AssetPrice.date <= price_end)
        .order_by(AssetPrice.ticker.asc(), AssetPrice.date.asc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [PricePoint(ticker=row.ticker.upper(), date=row.date, close=row.close) for row in rows]


async def run_backtest_for_market(
    session: AsyncSession,
    *,
    market: str,
    start_date: date,
    end_date: date,
    holding_period_days: int = 90,
    top_n: int = 5,
    rebalance_frequency: str = "monthly",
) -> dict[str, Any]:
    if market not in FEATURE_MODELS:
        raise ValueError(f"Mercado inválido para backtest: {market}")
    if start_date >= end_date:
        raise ValueError("start_date deve ser anterior a end_date")

    features = await _load_features(session, market=market, start_date=start_date, end_date=end_date)
    prices = await _load_prices(
        session,
        market=market,
        start_date=start_date,
        end_date=end_date,
        holding_period_days=holding_period_days,
    )
    return run_ranking_backtest(
        market=market,
        features=features,
        prices=prices,
        start_date=start_date,
        end_date=end_date,
        holding_period_days=holding_period_days,
        top_n=top_n,
        rebalance_frequency=rebalance_frequency,
    )


async def run_backtest_all_markets(
    session: AsyncSession,
    *,
    start_date: date,
    end_date: date,
    holding_period_days: int = 90,
    top_n: int = 5,
    rebalance_frequency: str = "monthly",
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for market in FEATURE_MODELS:
        output[market] = await run_backtest_for_market(
            session,
            market=market,
            start_date=start_date,
            end_date=end_date,
            holding_period_days=holding_period_days,
            top_n=top_n,
            rebalance_frequency=rebalance_frequency,
        )
    return output


async def get_backtest_summary(session: AsyncSession) -> dict[str, Any]:
    markets: list[dict[str, Any]] = []
    warnings: list[str] = []
    for market, model in FEATURE_MODELS.items():
        feature_stmt = select(func.count(model.id), func.max(model.date))
        feature_count, latest_feature_date = (await session.execute(feature_stmt)).one()
        price_stmt = select(func.count(AssetPrice.id), func.max(AssetPrice.date)).where(AssetPrice.market == market)
        price_count, latest_price_date = (await session.execute(price_stmt)).one()
        if not feature_count:
            warnings.append(f"{market}: sem features calculadas para backtest.")
        if not price_count:
            warnings.append(f"{market}: sem preços históricos para backtest.")
        markets.append(
            {
                "market": market,
                "feature_rows": int(feature_count or 0),
                "price_rows": int(price_count or 0),
                "latest_feature_date": latest_feature_date,
                "latest_price_date": latest_price_date,
            }
        )
    return {
        "markets": markets,
        "methodology": [
            "Resumo operacional das tabelas *_ml_features e asset_prices usadas no backtest base.",
            "Não há persistência de resultados de backtest nesta fase.",
        ],
        "warnings": warnings,
    }
