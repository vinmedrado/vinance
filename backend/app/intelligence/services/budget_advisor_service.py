from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.investment_recommendation_model import InvestmentRecommendation
from backend.app.intelligence.recommendation_guardrail_model import AssetRecommendationGuardrail
from backend.app.intelligence.services.recommendation_guardrail_service import APPROVED, GUARDRAIL_SOURCE, WARNING
from backend.app.intelligence.services.asset_score_service import SCORE_SOURCE, normalize_market
from backend.app.intelligence.services.investor_profile_service import (
    MODERATE,
    apply_profile_filters,
    calculate_profile_score,
    get_diversified_allocation,
    normalize_profile,
)
from backend.app.intelligence.asset_trend_signal_model import AssetTrendSignal
from backend.app.intelligence.services.recommendation_score_service import build_recommendation_components, calculate_recommendation_score
from backend.app.intelligence.services.recommendation_explanation_service import enrich_item_with_explanation
from backend.app.intelligence.services.trend_signal_service import TREND_SOURCE, latest_trend_date, normalize_trend_label, ticker_set_for_trend

DIVERSIFIED_ALLOCATION = get_diversified_allocation(MODERATE)


@dataclass
class BudgetAdvisorItem:
    ticker: str
    market: str
    score_total: Decimal
    price: Decimal
    quantity_possible: int
    invested_amount: Decimal
    status: str = APPROVED
    risk_level: str = "LOW"
    reasons_json: dict[str, Any] | None = None
    profile: str = MODERATE
    profile_score: Decimal | None = None
    score_value: Decimal | None = None
    score_quality: Decimal | None = None
    score_dividend: Decimal | None = None
    score_liquidity: Decimal | None = None
    score_risk: Decimal | None = None
    trend_label: str | None = None
    momentum_score: Decimal | None = None
    trend_confidence: str | None = None
    trend_method: str | None = None
    recommendation_score: Decimal | None = None
    recommendation_components_json: dict[str, Any] | None = None


def _as_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def _finite_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        normalized = Decimal(str(default if value is None else value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)
    return normalized if normalized.is_finite() else Decimal(default)


def _validate_budget(budget: Decimal) -> Decimal:
    try:
        budget = Decimal(str(budget))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("budget deve ser um número finito maior que zero") from exc
    if not budget.is_finite() or budget <= 0:
        raise ValueError("budget deve ser maior que zero")
    return budget


def _quantity_possible(budget: Decimal, price: Decimal) -> int:
    if price <= 0:
        return 0
    quantity = int((budget / price).to_integral_value(rounding=ROUND_DOWN))
    return max(quantity, 0)


async def _latest_score_date(session: AsyncSession, market: str):
    result = await session.execute(
        select(func.max(AssetScore.date)).where(
            AssetScore.market == market,
            AssetScore.source == SCORE_SOURCE,
        )
    )
    return result.scalar_one_or_none()


def build_budget_items(
    scores: list[AssetScore],
    *,
    budget: Decimal,
    limit: int,
    guardrails: dict[str, AssetRecommendationGuardrail] | None = None,
    include_warnings: bool = False,
    profile: str | None = None,
    allowed_tickers: set[str] | None = None,
    trend_signals: dict[str, AssetTrendSignal] | None = None,
) -> list[BudgetAdvisorItem]:
    budget = _validate_budget(budget)
    guardrails = guardrails or {}
    trend_signals = trend_signals or {}
    normalized_profile = normalize_profile(profile)
    allowed_statuses = {APPROVED, WARNING} if include_warnings else {APPROVED}
    items: list[BudgetAdvisorItem] = []
    seen_tickers: set[str] = set()
    for score in scores:
        normalized_ticker = str(score.ticker).strip().upper()
        if not normalized_ticker or normalized_ticker in seen_tickers:
            continue
        if allowed_tickers is not None and normalized_ticker not in allowed_tickers:
            continue
        guardrail = guardrails.get(normalized_ticker)
        status = guardrail.status if guardrail is not None else APPROVED
        if status == "BLOCKED" or status not in allowed_statuses:
            continue
        price = _finite_decimal(score.price)
        score_total = _finite_decimal(score.score_total)
        if price <= 0 or score_total <= 0:
            continue
        quantity = _quantity_possible(budget, price)
        if quantity < 1:
            continue
        trend_signal = trend_signals.get(score.ticker.upper())
        items.append(
            BudgetAdvisorItem(
                ticker=score.ticker,
                market=score.market,
                score_total=score_total,
                price=price,
                quantity_possible=quantity,
                invested_amount=_as_money(price * quantity),
                status=status,
                risk_level=guardrail.risk_level if guardrail is not None else "LOW",
                reasons_json=guardrail.reasons_json if guardrail is not None else {"blocked": [], "warnings": [], "summary": []},
                profile=normalized_profile,
                score_value=_finite_decimal(getattr(score, "score_value", None)),
                score_quality=_finite_decimal(getattr(score, "score_quality", None)),
                score_dividend=_finite_decimal(getattr(score, "score_dividend", None)),
                score_liquidity=_finite_decimal(getattr(score, "score_liquidity", None)),
                score_risk=_finite_decimal(getattr(score, "score_risk", None), "100"),
                trend_label=getattr(trend_signal, "trend_label", None) if trend_signal is not None else None,
                momentum_score=_finite_decimal(getattr(trend_signal, "momentum_score", None)) if trend_signal is not None else Decimal("0"),
                trend_confidence=(getattr(trend_signal, "metadata_json", {}) or {}).get("confidence_level") if trend_signal is not None else "VERY_LOW",
                trend_method=(getattr(trend_signal, "metadata_json", {}) or {}).get("trend_method") if trend_signal is not None else None,
            )
        )
        seen_tickers.add(normalized_ticker)
    items = apply_profile_filters(items, normalized_profile, include_warnings=include_warnings)
    for item in items:
        item.profile_score = calculate_profile_score(item, normalized_profile)
        trend_signal = trend_signals.get(item.ticker.upper())
        trend_label = item.trend_label if item.trend_label is not None else None
        trend_confidence = item.trend_confidence if item.trend_confidence is not None else None
        item.recommendation_score = calculate_recommendation_score(
            score_total=item.score_total,
            profile_score=item.profile_score,
            status=item.status,
            risk_level=item.risk_level,
            trend_label=trend_label,
            momentum_score=item.momentum_score,
            trend_confidence=trend_confidence,
            profile=normalized_profile,
        )
        item.recommendation_components_json = build_recommendation_components(
            score_total=item.score_total,
            profile_score=item.profile_score,
            status=item.status,
            risk_level=item.risk_level,
            trend_label=trend_label,
            momentum_score=item.momentum_score,
            trend_confidence=trend_confidence,
            profile=normalized_profile,
        )
    items.sort(key=lambda item: (-(item.recommendation_score or Decimal("0")), str(item.ticker)))
    return items[:limit]


async def list_budget_recommendations(
    session: AsyncSession,
    *,
    budget: Decimal,
    market: str,
    limit: int = 20,
    persist: bool = True,
    include_warnings: bool = False,
    profile: str | None = None,
    trend_filter: str | None = None,
) -> list[BudgetAdvisorItem]:
    budget = _validate_budget(budget)
    normalized_profile = normalize_profile(profile)
    normalized_trend = normalize_trend_label(trend_filter)
    normalized_market = normalize_market(market)
    latest_date = await _latest_score_date(session, normalized_market)
    if latest_date is None:
        return []

    result = await session.execute(
        select(AssetScore)
        .where(
            AssetScore.market == normalized_market,
            AssetScore.date == latest_date,
            AssetScore.source == SCORE_SOURCE,
            AssetScore.price > 0,
            AssetScore.score_total > 0,
        )
        .order_by(AssetScore.score_total.desc(), AssetScore.ticker.asc())
        .limit(max(limit * 8, limit, 100))
    )
    scores = list(result.scalars().all())
    guardrail_result = await session.execute(
        select(AssetRecommendationGuardrail).where(
            AssetRecommendationGuardrail.market == normalized_market,
            AssetRecommendationGuardrail.date == latest_date,
            AssetRecommendationGuardrail.source == GUARDRAIL_SOURCE,
        )
    )
    guardrails = {item.ticker.upper(): item for item in guardrail_result.scalars().all()}

    trend_signals: dict[str, AssetTrendSignal] = {}
    target_trend_date = await latest_trend_date(session, normalized_market)
    if target_trend_date is not None:
        trend_result = await session.execute(
            select(AssetTrendSignal).where(
                AssetTrendSignal.market == normalized_market,
                AssetTrendSignal.date == target_trend_date,
                AssetTrendSignal.source == TREND_SOURCE,
            )
        )
        trend_signals = {item.ticker.upper(): item for item in trend_result.scalars().all()}

    allowed_tickers = None
    if normalized_trend is not None:
        allowed_tickers = await ticker_set_for_trend(session, market=normalized_market, trend=normalized_trend)
    items = build_budget_items(
        scores,
        budget=budget,
        limit=limit,
        guardrails=guardrails,
        include_warnings=include_warnings,
        profile=normalized_profile,
        allowed_tickers=allowed_tickers,
        trend_signals=trend_signals,
    )
    if persist and items:
        session.add_all(
            InvestmentRecommendation(
                budget=_as_money(budget),
                market=item.market,
                ticker=item.ticker,
                score_total=item.score_total,
                price=item.price,
                quantity_possible=item.quantity_possible,
                invested_amount=item.invested_amount,
                recommendation_rank=rank,
            )
            for rank, item in enumerate(items, start=1)
        )
        await session.commit()
    return items


async def build_explained_budget_recommendations(
    session: AsyncSession,
    *,
    budget: Decimal,
    market: str,
    limit: int = 20,
    include_warnings: bool = False,
    profile: str | None = None,
    trend_filter: str | None = None,
) -> dict[str, Any]:
    """Return the Budget Advisor output with a business-friendly explanation.

    This function is intentionally derived/read-only: it reuses the existing
    Budget Advisor pipeline and only enriches the selected items at runtime.
    """
    budget = _validate_budget(budget)
    normalized_profile = normalize_profile(profile)
    normalized_market = normalize_market(market)
    items = await list_budget_recommendations(
        session,
        budget=budget,
        market=normalized_market,
        limit=limit,
        persist=False,
        include_warnings=include_warnings,
        profile=normalized_profile,
        trend_filter=trend_filter,
    )
    contexts = [
        {
            "total_candidates": len(items),
            "recommendation_rank": rank,
            "alternatives": [candidate for candidate in items if candidate.ticker != item.ticker],
            "budget": budget,
            "market": normalized_market,
            "profile": normalized_profile,
        }
        for rank, item in enumerate(items, start=1)
    ]
    best = enrich_item_with_explanation(items[0], budget=budget, summary=False, context=contexts[0]) if items else None
    alternatives = [
        enrich_item_with_explanation(item, budget=budget, summary=True, context=context)
        for item, context in zip(items[1:], contexts[1:])
    ]
    return {
        "budget": _as_money(budget),
        "market": normalized_market,
        "profile": normalized_profile,
        "best_recommendation": best,
        "alternatives": alternatives,
        "disclaimer": "Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno.",
    }


async def build_diversified_budget_advisor(
    session: AsyncSession,
    *,
    budget: Decimal,
    limit_per_market: int = 1,
    profile: str | None = None,
    include_warnings: bool = False,
) -> dict[str, Any]:
    budget = _validate_budget(budget)
    normalized_profile = normalize_profile(profile)
    diversified_allocation = get_diversified_allocation(normalized_profile)
    allocation_rows: list[dict[str, Any]] = []
    total_invested = Decimal("0.00")

    for market, weight in diversified_allocation.items():
        if weight <= 0:
            continue
        allocated_budget = _as_money(budget * weight)
        items = await list_budget_recommendations(
            session,
            budget=allocated_budget,
            market=market,
            limit=limit_per_market,
            persist=False,
            include_warnings=include_warnings,
            profile=normalized_profile,
        )
        for item in items:
            total_invested += item.invested_amount
            allocation_rows.append(
                {
                    "allocation": str((weight * Decimal("100")).quantize(Decimal("0.01"))),
                    "market": item.market,
                    "ticker": item.ticker,
                    "quantity": item.quantity_possible,
                    "price": item.price,
                    "invested_amount": item.invested_amount,
                    "score_total": item.score_total,
                    "profile": item.profile,
                    "profile_score": item.profile_score or item.score_total,
                    "recommendation_score": item.recommendation_score,
                    "recommendation_components_json": item.recommendation_components_json or {},
                    "trend_label": item.trend_label,
                    "momentum_score": item.momentum_score,
                    "trend_confidence": item.trend_confidence,
                    "trend_method": item.trend_method,
                    "status": item.status,
                    "risk_level": item.risk_level,
                    "reasons_json": item.reasons_json or {},
                }
            )

    return {
        "budget": _as_money(budget),
        "profile": normalized_profile,
        "total_invested": _as_money(total_invested),
        "remaining_budget": _as_money(budget - total_invested),
        "allocation": allocation_rows,
    }
