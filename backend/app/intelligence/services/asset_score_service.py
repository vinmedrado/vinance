from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.market.models.acoes import AcaoFundamental
from backend.app.market.models.bdr import BdrFundamental
from backend.app.market.models.etf import EtfFundamental
from backend.app.market.models.fii import FiiFundamental

SCORE_SOURCE = "vinance_score_v1"


@dataclass(frozen=True)
class MetricRule:
    field: str
    component: str
    higher_is_better: bool = True
    ignore_non_positive: bool = False


MARKET_MODELS = {
    "FII": FiiFundamental,
    "FIIS": FiiFundamental,
    "ACOES": AcaoFundamental,
    "AÇÕES": AcaoFundamental,
    "ETF": EtfFundamental,
    "ETFS": EtfFundamental,
    "BDR": BdrFundamental,
    "BDRS": BdrFundamental,
}

MARKET_OUTPUT = {"FIIS": "FII", "FII": "FII", "ACOES": "ACOES", "AÇÕES": "ACOES", "ETF": "ETF", "ETFS": "ETF", "BDR": "BDR", "BDRS": "BDR"}

MARKET_RULES: dict[str, list[MetricRule]] = {
    "FII": [
        MetricRule("pvp", "value", higher_is_better=False),
        MetricRule("dy_12m", "dividend"),
        MetricRule("liquidez_diaria", "liquidity"),
        MetricRule("num_cotistas", "quality"),
        MetricRule("vacancia_fisica", "risk", higher_is_better=False),
    ],
    "ACOES": [
        MetricRule("pl", "value", higher_is_better=False, ignore_non_positive=True),
        MetricRule("pvp", "value", higher_is_better=False),
        MetricRule("roe", "quality"),
        MetricRule("roic", "quality"),
        MetricRule("dy_12m", "dividend"),
        MetricRule("market_cap", "quality"),
        MetricRule("volume_medio_diario", "liquidity"),
    ],
    "ETF": [
        MetricRule("taxa_adm", "value", higher_is_better=False),
        MetricRule("retorno_12m", "quality"),
        MetricRule("patrimonio_liq", "quality"),
        MetricRule("volume_medio_diario", "liquidity"),
        MetricRule("num_cotistas", "liquidity"),
    ],
    "BDR": [
        MetricRule("pl", "value", higher_is_better=False, ignore_non_positive=True),
        MetricRule("pvp", "value", higher_is_better=False),
        MetricRule("dy_12m", "dividend"),
        MetricRule("market_cap", "quality"),
        MetricRule("volume_medio_diario_brl", "liquidity"),
    ],
}


def normalize_market(market: str) -> str:
    normalized = (market or "").strip().upper()
    if normalized not in MARKET_OUTPUT:
        raise ValueError(f"Mercado não suportado para scoring: {market}")
    return MARKET_OUTPUT[normalized]


def _to_float(value: Any, *, ignore_non_positive: bool = False) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if ignore_non_positive and number <= 0:
        return None
    return number


def _round_score(value: float | None) -> Decimal | None:
    if value is None:
        return None
    value = max(0.0, min(100.0, float(value)))
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _percentile_scores(rows: list[Any], rule: MetricRule) -> dict[str, float]:
    values: list[tuple[str, float]] = []
    for row in rows:
        value = _to_float(getattr(row, rule.field, None), ignore_non_positive=rule.ignore_non_positive)
        if value is not None:
            values.append((row.ticker.upper(), value))
    if not values:
        return {}

    values.sort(key=lambda item: item[1])
    n = len(values)
    if n == 1:
        base = {values[0][0]: 100.0}
    else:
        base = {ticker: (idx / (n - 1)) * 100 for idx, (ticker, _value) in enumerate(values)}
    if rule.higher_is_better:
        return base
    return {ticker: 100.0 - score for ticker, score in base.items()}


def calculate_scores_for_rows(rows: list[Any], market: str, *, source: str = SCORE_SOURCE) -> list[dict[str, Any]]:
    market = normalize_market(market)
    rules = MARKET_RULES[market]
    metric_scores = {rule.field: _percentile_scores(rows, rule) for rule in rules}
    payloads: list[dict[str, Any]] = []

    for row in rows:
        ticker = row.ticker.upper()
        components: dict[str, list[float]] = {"value": [], "quality": [], "dividend": [], "liquidity": [], "risk": []}
        metrics: dict[str, Any] = {}
        available = 0
        for rule in rules:
            raw = _to_float(getattr(row, rule.field, None), ignore_non_positive=rule.ignore_non_positive)
            score = metric_scores[rule.field].get(ticker)
            metrics[rule.field] = {"raw": raw, "score": score, "component": rule.component}
            if score is not None:
                available += 1
                components[rule.component].append(score)

        component_scores = {
            name: (sum(values) / len(values) if values else None)
            for name, values in components.items()
        }
        valid_components = [value for value in component_scores.values() if value is not None]
        base_total = sum(valid_components) / len(valid_components) if valid_components else 0.0
        coverage = available / max(len(rules), 1)
        confidence_multiplier = 0.70 + (0.30 * coverage)
        total = base_total * confidence_multiplier

        payloads.append(
            {
                "ticker": ticker,
                "market": market,
                "date": row.date,
                "score_total": _round_score(total) or Decimal("0.0000"),
                "score_value": _round_score(component_scores["value"]),
                "score_quality": _round_score(component_scores["quality"]),
                "score_dividend": _round_score(component_scores["dividend"]),
                "score_liquidity": _round_score(component_scores["liquidity"]),
                "score_risk": _round_score(component_scores["risk"]),
                "price": getattr(row, "price", None),
                "metadata_json": {
                    "version": source,
                    "coverage": round(coverage, 4),
                    "available_metrics": available,
                    "total_metrics": len(rules),
                    "metrics": metrics,
                },
                "source": source,
            }
        )
    return payloads


async def get_latest_fundamental_date(session: AsyncSession, market: str) -> date | None:
    model = MARKET_MODELS[normalize_market(market)]
    result = await session.execute(select(func.max(model.date)))
    return result.scalar_one_or_none()


async def list_latest_fundamentals(session: AsyncSession, market: str, target_date: date) -> list[Any]:
    model = MARKET_MODELS[normalize_market(market)]
    result = await session.execute(select(model).where(model.date == target_date))
    return list(result.scalars().all())


async def upsert_asset_scores(session: AsyncSession, payloads: Iterable[dict[str, Any]]) -> int:
    rows = list(payloads)
    if not rows:
        return 0
    stmt = pg_insert(AssetScore).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_scores_ticker_market_date_source",
        set_={
            "score_total": excluded.score_total,
            "score_value": excluded.score_value,
            "score_quality": excluded.score_quality,
            "score_dividend": excluded.score_dividend,
            "score_liquidity": excluded.score_liquidity,
            "score_risk": excluded.score_risk,
            "price": excluded.price,
            "metadata_json": excluded.metadata_json,
            "calculated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def calculate_market_scores(session: AsyncSession, market: str, *, source: str = SCORE_SOURCE) -> dict[str, Any]:
    normalized_market = normalize_market(market)
    latest_date = await get_latest_fundamental_date(session, normalized_market)
    if latest_date is None:
        return {"market": normalized_market, "status": "SKIPPED", "reason": "sem fundamentals", "saved": 0}
    rows = await list_latest_fundamentals(session, normalized_market, latest_date)
    payloads = calculate_scores_for_rows(rows, normalized_market, source=source)
    saved = await upsert_asset_scores(session, payloads)
    return {"market": normalized_market, "date": str(latest_date), "status": "SUCCESS", "total": len(rows), "saved": saved, "source": source}


async def calculate_all_asset_scores(session: AsyncSession, *, source: str = SCORE_SOURCE) -> dict[str, Any]:
    results = []
    for market in ("FII", "ACOES", "ETF", "BDR"):
        results.append(await calculate_market_scores(session, market, source=source))
    return {"status": "SUCCESS", "source": source, "markets": results, "saved": sum(int(item.get("saved") or 0) for item in results)}


async def list_rankings(session: AsyncSession, *, market: str, limit: int = 20) -> list[AssetScore]:
    normalized_market = normalize_market(market)
    latest_result = await session.execute(select(func.max(AssetScore.date)).where(AssetScore.market == normalized_market, AssetScore.source == SCORE_SOURCE))
    latest_date = latest_result.scalar_one_or_none()
    if latest_date is None:
        return []
    result = await session.execute(
        select(AssetScore)
        .where(AssetScore.market == normalized_market, AssetScore.date == latest_date, AssetScore.source == SCORE_SOURCE)
        .order_by(AssetScore.score_total.desc(), AssetScore.ticker.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
