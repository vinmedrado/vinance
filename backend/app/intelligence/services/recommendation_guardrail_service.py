from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.recommendation_guardrail_model import AssetRecommendationGuardrail
from backend.app.intelligence.services.asset_score_service import MARKET_MODELS, SCORE_SOURCE, normalize_market

GUARDRAIL_SOURCE = "vinance_guardrail_v1"
APPROVED = "APPROVED"
WARNING = "WARNING"
BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class GuardrailDecision:
    ticker: str
    market: str
    date: date
    status: str
    risk_level: str
    penalty_score: Decimal
    reasons_json: dict[str, Any]
    source: str = GUARDRAIL_SOURCE


def _number(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def _lte(value: Any, threshold: str) -> bool:
    number = _number(value)
    return number is not None and number <= Decimal(threshold)


def _lt(value: Any, threshold: str) -> bool:
    number = _number(value)
    return number is not None and number < Decimal(threshold)


def _gte(value: Any, threshold: str) -> bool:
    number = _number(value)
    return number is not None and number >= Decimal(threshold)


def _gt(value: Any, threshold: str) -> bool:
    number = _number(value)
    return number is not None and number > Decimal(threshold)


def _add(reasons: list[dict[str, Any]], *, code: str, field: str, value: Any, rule: str, severity: str) -> None:
    raw = _number(value)
    reasons.append(
        {
            "code": code,
            "field": field,
            "value": float(raw) if raw is not None else None,
            "rule": rule,
            "severity": severity,
        }
    )


def _penalty(blocked: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> Decimal:
    value = (len(blocked) * Decimal("35")) + (len(warnings) * Decimal("10"))
    return min(value, Decimal("100")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def evaluate_guardrail(score: AssetScore, fundamental: Any | None, *, source: str = GUARDRAIL_SOURCE) -> GuardrailDecision:
    market = normalize_market(score.market)
    blocked: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def field(name: str) -> Any:
        if name == "score_total":
            return score.score_total
        if name == "price":
            return score.price
        return getattr(fundamental, name, None) if fundamental is not None else None

    if _lte(field("price"), "0"):
        _add(blocked, code="INVALID_PRICE", field="price", value=field("price"), rule="price <= 0", severity="BLOCKED")
    if _lte(field("score_total"), "0"):
        _add(blocked, code="INVALID_SCORE", field="score_total", value=field("score_total"), rule="score_total <= 0", severity="BLOCKED")

    if market == "FII":
        if _lte(field("pvp"), "0"):
            _add(blocked, code="INVALID_PVP", field="pvp", value=field("pvp"), rule="pvp <= 0", severity="BLOCKED")
        if _gte(field("dy_12m"), "30"):
            _add(blocked, code="EXTREME_DY", field="dy_12m", value=field("dy_12m"), rule="dy_12m >= 30", severity="BLOCKED")
        if _lte(field("liquidez_diaria"), "50000"):
            _add(blocked, code="CRITICAL_LIQUIDITY", field="liquidez_diaria", value=field("liquidez_diaria"), rule="liquidez_diaria <= 50000", severity="BLOCKED")
        if _lte(field("num_cotistas"), "1000"):
            _add(blocked, code="CRITICAL_HOLDERS", field="num_cotistas", value=field("num_cotistas"), rule="num_cotistas <= 1000", severity="BLOCKED")

        if _gte(field("dy_12m"), "18"):
            _add(warnings, code="HIGH_DY", field="dy_12m", value=field("dy_12m"), rule="dy_12m >= 18", severity="WARNING")
        if _lt(field("pvp"), "0.50"):
            _add(warnings, code="LOW_PVP", field="pvp", value=field("pvp"), rule="pvp < 0.50", severity="WARNING")
        if _lt(field("liquidez_diaria"), "200000"):
            _add(warnings, code="LOW_LIQUIDITY", field="liquidez_diaria", value=field("liquidez_diaria"), rule="liquidez_diaria < 200000", severity="WARNING")
        if _lt(field("num_cotistas"), "10000"):
            _add(warnings, code="LOW_HOLDERS", field="num_cotistas", value=field("num_cotistas"), rule="num_cotistas < 10000", severity="WARNING")
        if _gte(field("vacancia_fisica"), "20"):
            _add(warnings, code="HIGH_VACANCY", field="vacancia_fisica", value=field("vacancia_fisica"), rule="vacancia_fisica >= 20", severity="WARNING")

    elif market == "ACOES":
        for name in ("pl", "pvp", "roe"):
            if _lte(field(name), "0"):
                _add(blocked, code=f"INVALID_{name.upper()}", field=name, value=field(name), rule=f"{name} <= 0", severity="BLOCKED")
        if _gt(field("pl"), "40"):
            _add(warnings, code="HIGH_PL", field="pl", value=field("pl"), rule="pl > 40", severity="WARNING")
        if _gt(field("pvp"), "5"):
            _add(warnings, code="HIGH_PVP", field="pvp", value=field("pvp"), rule="pvp > 5", severity="WARNING")
        if _gt(field("dy_12m"), "20"):
            _add(warnings, code="HIGH_DY", field="dy_12m", value=field("dy_12m"), rule="dy_12m > 20", severity="WARNING")
        if _lt(field("roe"), "5"):
            _add(warnings, code="LOW_ROE", field="roe", value=field("roe"), rule="roe < 5", severity="WARNING")
        if _lt(field("market_cap"), "1000000000"):
            _add(warnings, code="LOW_MARKET_CAP", field="market_cap", value=field("market_cap"), rule="market_cap < 1B", severity="WARNING")
        if _lt(field("volume_medio_diario"), "1000000"):
            _add(warnings, code="LOW_VOLUME", field="volume_medio_diario", value=field("volume_medio_diario"), rule="volume_medio_diario < 1M", severity="WARNING")

    elif market == "ETF":
        if _gt(field("taxa_adm"), "1.00"):
            _add(warnings, code="HIGH_ADMIN_FEE", field="taxa_adm", value=field("taxa_adm"), rule="taxa_adm > 1.00", severity="WARNING")
        if _lt(field("volume_medio_diario"), "200000"):
            _add(warnings, code="LOW_VOLUME", field="volume_medio_diario", value=field("volume_medio_diario"), rule="volume_medio_diario < 200k", severity="WARNING")
        if _lt(field("patrimonio_liq"), "100000000"):
            _add(warnings, code="LOW_AUM", field="patrimonio_liq", value=field("patrimonio_liq"), rule="patrimonio_liq < 100M", severity="WARNING")
        if _lt(field("retorno_12m"), "-20"):
            _add(warnings, code="NEGATIVE_RETURN", field="retorno_12m", value=field("retorno_12m"), rule="retorno_12m < -20", severity="WARNING")

    elif market == "BDR":
        if _lt(field("volume_medio_diario_brl"), "200000"):
            _add(warnings, code="LOW_VOLUME", field="volume_medio_diario_brl", value=field("volume_medio_diario_brl"), rule="volume_medio_diario_brl < 200k", severity="WARNING")
        if _lt(field("market_cap"), "10000000000"):
            _add(warnings, code="LOW_MARKET_CAP", field="market_cap", value=field("market_cap"), rule="market_cap < 10B", severity="WARNING")
        if _gt(field("dy_12m"), "20"):
            _add(warnings, code="HIGH_DY", field="dy_12m", value=field("dy_12m"), rule="dy_12m > 20", severity="WARNING")
        if _lte(field("pl"), "0"):
            _add(warnings, code="INVALID_PL", field="pl", value=field("pl"), rule="pl <= 0", severity="WARNING")

    if blocked:
        status = BLOCKED
        risk_level = "HIGH"
    elif warnings:
        status = WARNING
        risk_level = "MEDIUM"
    else:
        status = APPROVED
        risk_level = "LOW"

    return GuardrailDecision(
        ticker=score.ticker.upper(),
        market=market,
        date=score.date,
        status=status,
        risk_level=risk_level,
        penalty_score=_penalty(blocked, warnings),
        reasons_json={
            "blocked": blocked,
            "warnings": warnings,
            "summary": [item["code"] for item in [*blocked, *warnings]],
        },
        source=source,
    )


async def _latest_score_date(session: AsyncSession, market: str) -> date | None:
    result = await session.execute(
        select(func.max(AssetScore.date)).where(AssetScore.market == normalize_market(market), AssetScore.source == SCORE_SOURCE)
    )
    return result.scalar_one_or_none()


async def _fundamentals_by_ticker(session: AsyncSession, market: str, target_date: date) -> dict[str, Any]:
    model = MARKET_MODELS[normalize_market(market)]
    result = await session.execute(select(model).where(model.date == target_date))
    return {row.ticker.upper(): row for row in result.scalars().all()}


async def upsert_guardrails(session: AsyncSession, decisions: Iterable[GuardrailDecision]) -> int:
    rows = [decision.__dict__ for decision in decisions]
    if not rows:
        return 0
    stmt = pg_insert(AssetRecommendationGuardrail).values(rows)
    excluded = stmt.excluded
    stmt = stmt.on_conflict_do_update(
        constraint="uq_asset_recommendation_guardrails_ticker_market_date_source",
        set_={
            "status": excluded.status,
            "risk_level": excluded.risk_level,
            "penalty_score": excluded.penalty_score,
            "reasons_json": excluded.reasons_json,
            "calculated_at": func.now(),
        },
    )
    await session.execute(stmt)
    await session.commit()
    return len(rows)


async def calculate_market_guardrails(session: AsyncSession, market: str, *, source: str = GUARDRAIL_SOURCE) -> dict[str, Any]:
    normalized_market = normalize_market(market)
    latest_date = await _latest_score_date(session, normalized_market)
    if latest_date is None:
        return {"market": normalized_market, "status": "SKIPPED", "reason": "sem asset_scores", "saved": 0}

    score_result = await session.execute(
        select(AssetScore).where(
            AssetScore.market == normalized_market,
            AssetScore.date == latest_date,
            AssetScore.source == SCORE_SOURCE,
        )
    )
    scores = list(score_result.scalars().all())
    fundamentals = await _fundamentals_by_ticker(session, normalized_market, latest_date)
    decisions = [evaluate_guardrail(score, fundamentals.get(score.ticker.upper()), source=source) for score in scores]
    saved = await upsert_guardrails(session, decisions)
    status_counts: dict[str, int] = {APPROVED: 0, WARNING: 0, BLOCKED: 0}
    for decision in decisions:
        status_counts[decision.status] = status_counts.get(decision.status, 0) + 1
    return {
        "market": normalized_market,
        "date": str(latest_date),
        "status": "SUCCESS",
        "total": len(scores),
        "saved": saved,
        "source": source,
        "status_counts": status_counts,
    }


async def calculate_all_recommendation_guardrails(session: AsyncSession, *, source: str = GUARDRAIL_SOURCE) -> dict[str, Any]:
    results = []
    for market in ("FII", "ACOES", "ETF", "BDR"):
        results.append(await calculate_market_guardrails(session, market, source=source))
    return {"status": "SUCCESS", "source": source, "markets": results, "saved": sum(int(item.get("saved") or 0) for item in results)}


async def list_guardrails(
    session: AsyncSession,
    *,
    market: str,
    status: str | None = None,
    limit: int = 50,
    source: str = GUARDRAIL_SOURCE,
) -> list[AssetRecommendationGuardrail]:
    normalized_market = normalize_market(market)
    latest_result = await session.execute(
        select(func.max(AssetRecommendationGuardrail.date)).where(
            AssetRecommendationGuardrail.market == normalized_market,
            AssetRecommendationGuardrail.source == source,
        )
    )
    latest_date = latest_result.scalar_one_or_none()
    if latest_date is None:
        return []
    filters = [
        AssetRecommendationGuardrail.market == normalized_market,
        AssetRecommendationGuardrail.date == latest_date,
        AssetRecommendationGuardrail.source == source,
    ]
    if status:
        normalized_status = status.strip().upper()
        if normalized_status not in {APPROVED, WARNING, BLOCKED}:
            raise ValueError(f"status inválido: {status}")
        filters.append(AssetRecommendationGuardrail.status == normalized_status)
    result = await session.execute(
        select(AssetRecommendationGuardrail)
        .where(*filters)
        .order_by(AssetRecommendationGuardrail.status.asc(), AssetRecommendationGuardrail.penalty_score.desc(), AssetRecommendationGuardrail.ticker.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
