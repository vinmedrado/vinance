from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.investment_decisions.models import InvestmentDecisionAudit
from backend.app.investment_performance.config import (
    EVALUATION_POLICY_VERSION,
    EVALUATION_PRICE_TOLERANCE_DAYS,
    HORIZON_DAYS,
    PRICE_SOURCE_PRIORITY,
    REFERENCE_PRICE_TOLERANCE_DAYS,
)
from backend.app.investment_performance.evaluator import (
    build_result_context,
    calculate_excursions,
    calculate_observed_change,
    classify_result,
)
from backend.app.investment_performance.metrics import build_performance_summary
from backend.app.investment_performance.repository import (
    get_owned_decision,
    insert_performances_if_absent,
    list_existing_horizons,
    list_performances_for_decisions,
    list_prices,
    list_valid_decisions,
)
from backend.app.market.models.prices import AssetPrice


UTC = timezone.utc
DECISION_SNAPSHOT_SOURCE = "decision_snapshot"
MARKET_ALIASES = {
    "FII": "fii",
    "FIIS": "fii",
    "ACOES": "acoes",
    "AÇÃO": "acoes",
    "AÇÕES": "acoes",
    "ETF": "etf",
    "ETFS": "etf",
    "BDR": "bdr",
    "BDRS": "bdr",
    "CRIPTO": "cripto",
    "CRYPTO": "cripto",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _positive_decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def normalize_market(value: str) -> str:
    normalized = value.strip().upper()
    return MARKET_ALIASES.get(normalized, normalized.lower())


def observation_timestamp(day: date) -> datetime:
    """Daily prices become observable only at the conservative UTC end of day."""

    return datetime.combine(day, time.max, tzinfo=UTC)


def _source_rank(source: str) -> tuple[int, str]:
    normalized = str(source or "").strip().lower()
    try:
        priority = PRICE_SOURCE_PRIORITY.index(normalized)
    except ValueError:
        priority = len(PRICE_SOURCE_PRIORITY)
    return priority, normalized


def _sort_prices(prices: Iterable[AssetPrice], *, newest_first: bool = False) -> list[AssetPrice]:
    if newest_first:
        return sorted(
            prices,
            key=lambda item: (-item.date.toordinal(), *_source_rank(item.source), item.id or 0),
        )
    return sorted(
        prices,
        key=lambda item: (item.date.toordinal(), *_source_rank(item.source), item.id or 0),
    )


async def resolve_reference_price(
    session: AsyncSession,
    decision: InvestmentDecisionAudit,
    *,
    as_of: datetime,
) -> tuple[Decimal, datetime, str] | None:
    decision_at = _as_utc(decision.created_at)
    snapshot_price = _positive_decimal(decision.price)
    if snapshot_price is not None:
        return snapshot_price, decision_at, DECISION_SNAPSHOT_SOURCE

    decision_day = decision_at.date()
    prices = await list_prices(
        session,
        ticker=str(decision.asset),
        market=normalize_market(str(decision.market)),
        date_from=decision_day - timedelta(days=REFERENCE_PRICE_TOLERANCE_DAYS),
        date_to=decision_day - timedelta(days=1),
        available_at=as_of,
    )
    for price in _sort_prices(prices, newest_first=True):
        close = _positive_decimal(price.close)
        timestamp = observation_timestamp(price.date)
        if close is not None and timestamp < decision_at:
            return close, timestamp, str(price.source)
    return None


async def resolve_evaluation_price(
    session: AsyncSession,
    decision: InvestmentDecisionAudit,
    *,
    target_at: datetime,
    as_of: datetime,
    preferred_source: str | None,
) -> tuple[AssetPrice, datetime] | None:
    prices = await list_prices(
        session,
        ticker=str(decision.asset),
        market=normalize_market(str(decision.market)),
        date_from=target_at.date(),
        date_to=target_at.date() + timedelta(days=EVALUATION_PRICE_TOLERANCE_DAYS),
        available_at=as_of,
        source=preferred_source,
    )
    for price in _sort_prices(prices):
        timestamp = observation_timestamp(price.date)
        if timestamp >= target_at and timestamp <= as_of and _positive_decimal(price.close) is not None:
            return price, timestamp
    return None


async def _resolve_excursions(
    session: AsyncSession,
    decision: InvestmentDecisionAudit,
    *,
    reference_price: Decimal,
    evaluation_price: AssetPrice,
    as_of: datetime,
) -> tuple[Decimal | None, Decimal | None]:
    decision_day = _as_utc(decision.created_at).date()
    prices = await list_prices(
        session,
        ticker=str(decision.asset),
        market=normalize_market(str(decision.market)),
        date_from=decision_day + timedelta(days=1),
        date_to=evaluation_price.date,
        available_at=as_of,
        source=str(evaluation_price.source),
    )
    highs = [value for item in prices if (value := _positive_decimal(item.high)) is not None]
    lows = [value for item in prices if (value := _positive_decimal(item.low)) is not None]
    return calculate_excursions(reference_price, highs, lows)


async def process_due_evaluations(
    session: AsyncSession,
    *,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    effective_as_of = _as_utc(as_of or _now_utc())
    decisions = await list_valid_decisions(
        session,
        matured_before=effective_as_of - timedelta(days=min(HORIZON_DAYS.values())),
    )
    existing = await list_existing_horizons(
        session,
        [decision.decision_id for decision in decisions],
    )

    rows: list[dict[str, Any]] = []
    eligible = 0
    already_evaluated = 0
    pending_prices = 0

    for decision in decisions:
        decision_at = _as_utc(decision.created_at)
        reference: tuple[Decimal, datetime, str] | None = None
        for horizon, days in HORIZON_DAYS.items():
            target_at = decision_at + timedelta(days=days)
            if target_at > effective_as_of:
                continue
            eligible += 1
            if horizon in existing.get(decision.decision_id, set()):
                already_evaluated += 1
                continue

            if reference is None:
                reference = await resolve_reference_price(session, decision, as_of=effective_as_of)
            if reference is None:
                pending_prices += 1
                continue
            reference_price, reference_timestamp, reference_source = reference
            preferred_source = None if reference_source == DECISION_SNAPSHOT_SOURCE else reference_source
            observation = await resolve_evaluation_price(
                session,
                decision,
                target_at=target_at,
                as_of=effective_as_of,
                preferred_source=preferred_source,
            )
            if observation is None:
                pending_prices += 1
                continue

            price_row, evaluation_timestamp = observation
            evaluation_price = _positive_decimal(price_row.close)
            if evaluation_price is None:
                pending_prices += 1
                continue
            absolute_change, return_pct = calculate_observed_change(
                reference_price,
                evaluation_price,
            )
            classification = classify_result(decision.recommendation, return_pct)
            favorable, adverse = await _resolve_excursions(
                session,
                decision,
                reference_price=reference_price,
                evaluation_price=price_row,
                as_of=effective_as_of,
            )
            rows.append(
                {
                    "decision_id": decision.decision_id,
                    "horizon": horizon,
                    "reference_price": reference_price,
                    "reference_price_timestamp": reference_timestamp,
                    "price_source": reference_source,
                    "evaluation_price": evaluation_price,
                    "evaluation_timestamp": evaluation_timestamp,
                    "evaluation_price_source": str(price_row.source),
                    "absolute_change": absolute_change,
                    "return_pct": return_pct,
                    "max_favorable_excursion_pct": favorable,
                    "max_adverse_excursion_pct": adverse,
                    "result_status": "EVALUATED",
                    "result_classification": classification,
                    "result_context": build_result_context(
                        decision.recommendation,
                        return_pct,
                        classification,
                    ),
                    "evaluation_policy_version": EVALUATION_POLICY_VERSION,
                    "evaluated_at": effective_as_of,
                }
            )

    created = await insert_performances_if_absent(session, rows)
    return {
        "status": "SUCCESS",
        "decisions_scanned": len(decisions),
        "eligible": eligible,
        "already_evaluated": already_evaluated,
        "pending_prices": pending_prices,
        "candidates": len(rows),
        "created": created,
        "duplicates_skipped": len(rows) - created,
        "as_of": effective_as_of.isoformat(),
        "evaluation_policy_version": EVALUATION_POLICY_VERSION,
    }


def _evaluation_payload(item: Any) -> dict[str, Any]:
    return {
        "horizon": item.horizon,
        "reference_price": item.reference_price,
        "reference_price_timestamp": item.reference_price_timestamp,
        "price_source": item.price_source,
        "evaluation_price": item.evaluation_price,
        "evaluation_timestamp": item.evaluation_timestamp,
        "evaluation_price_source": item.evaluation_price_source,
        "absolute_change": item.absolute_change,
        "return_pct": item.return_pct,
        "max_favorable_excursion_pct": item.max_favorable_excursion_pct,
        "max_adverse_excursion_pct": item.max_adverse_excursion_pct,
        "result_status": item.result_status,
        "result_classification": item.result_classification,
        "result_context": item.result_context,
        "evaluation_policy_version": item.evaluation_policy_version,
        "evaluated_at": item.evaluated_at,
    }


async def get_decision_performance(
    session: AsyncSession,
    *,
    user_id: int,
    decision_id: str,
    as_of: datetime | None = None,
) -> dict[str, Any] | None:
    decision = await get_owned_decision(
        session,
        user_id=user_id,
        decision_id=decision_id,
    )
    if decision is None:
        return None
    evaluations = await list_performances_for_decisions(session, [decision_id])
    evaluated_horizons = {item.horizon for item in evaluations}
    effective_as_of = _as_utc(as_of or _now_utc())
    reference = (
        (
            evaluations[0].reference_price,
            evaluations[0].reference_price_timestamp,
            evaluations[0].price_source,
        )
        if evaluations
        else await resolve_reference_price(session, decision, as_of=effective_as_of)
    )
    immature = [
        horizon
        for horizon, days in HORIZON_DAYS.items()
        if horizon not in evaluated_horizons
        and _as_utc(decision.created_at) + timedelta(days=days) > effective_as_of
    ]
    eligible_pending = [
        horizon
        for horizon, days in HORIZON_DAYS.items()
        if horizon not in evaluated_horizons
        and _as_utc(decision.created_at) + timedelta(days=days) <= effective_as_of
    ]
    return {
        "decision_id": decision.decision_id,
        "asset": decision.asset,
        "action": decision.recommendation,
        "decision_created_at": decision.created_at,
        "risk_level": decision.risk_level,
        "confidence": decision.confidence,
        "trend": decision.trend,
        "recommendation_score": decision.recommendation_score,
        "investor_profile": decision.investor_profile,
        "rule_version": decision.rule_version,
        "recommendation_engine_version": decision.recommendation_engine_version,
        "score_version": decision.score_version,
        "guardrail_version": decision.guardrail_version,
        "reference_price": reference[0] if reference else None,
        "reference_price_timestamp": reference[1] if reference else None,
        "price_source": reference[2] if reference else None,
        "evaluations": [_evaluation_payload(item) for item in evaluations],
        "pending_horizons": [
            horizon for horizon in HORIZON_DAYS if horizon not in evaluated_horizons
        ],
        "eligible_pending_horizons": eligible_pending,
        "immature_horizons": immature,
    }


async def get_performance_summary(
    session: AsyncSession,
    *,
    user_id: int,
    asset: str | None = None,
    action: str | None = None,
    horizon: str | None = None,
    risk_level: str | None = None,
    investor_profile: str | None = None,
    rule_version: str | None = None,
    recommendation_engine_version: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    decisions = await list_valid_decisions(
        session,
        user_id=user_id,
        asset=asset,
        action=action,
        risk_level=risk_level,
        investor_profile=investor_profile,
        rule_version=rule_version,
        recommendation_engine_version=recommendation_engine_version,
        date_from=date_from,
        date_to=date_to,
    )
    evaluations = await list_performances_for_decisions(
        session,
        [decision.decision_id for decision in decisions],
        horizon=horizon,
    )
    return build_performance_summary(
        decisions,
        evaluations,
        as_of=_as_utc(as_of or _now_utc()),
        horizon=horizon,
    )
