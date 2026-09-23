from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Any, Mapping

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.catalog.models import AssetCatalog
from backend.app.financial.models import FinancialProfile
from backend.app.intelligence.asset_score_model import AssetScore
from backend.app.intelligence.asset_trend_signal_model import AssetTrendSignal
from backend.app.intelligence.recommendation_guardrail_model import (
    AssetRecommendationGuardrail,
)
from backend.app.intelligence.services.asset_score_service import SCORE_SOURCE
from backend.app.intelligence.services.budget_advisor_service import build_budget_items
from backend.app.intelligence.services.investor_profile_service import VALID_PROFILES
from backend.app.intelligence.services.recommendation_explanation_service import (
    enrich_item_with_explanation,
)
from backend.app.intelligence.services.recommendation_guardrail_service import (
    GUARDRAIL_SOURCE,
)
from backend.app.intelligence.services.trend_signal_service import TREND_SOURCE
from backend.app.investment_orchestrator.rules import (
    MARKET_FRESHNESS_DAYS,
    PROFILE_ORDER,
    SETTLEMENT_CURRENCY,
    SUPPORTED_MARKETS,
)


MARKET_LABELS = {
    "ACOES": "Ações",
    "FII": "Fundos imobiliários",
    "ETF": "ETFs",
    "BDR": "BDRs",
}


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


async def load_profile_context(
    session: AsyncSession,
    *,
    normalized_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Load explicit profiles for active members without applying a default."""

    members = [
        item
        for item in list(normalized_inputs.get("members") or [])
        if item.get("status") == "ACTIVE"
    ]
    user_ids = sorted({int(item["user_id"]) for item in members})
    if not user_ids:
        return {
            "status": "MISSING",
            "effective_profile": None,
            "investment_horizon": None,
            "members": [],
            "missing_member_user_ids": [],
            "inconsistent_member_user_ids": [],
            "source": "financial_profiles.risk_profile",
        }

    result = await session.execute(
        select(FinancialProfile).where(FinancialProfile.user_id.in_(user_ids))
    )
    by_user = {int(item.user_id): item for item in result.scalars().all()}
    rows: list[dict[str, Any]] = []
    missing: list[int] = []
    inconsistent: list[int] = []
    known: list[str] = []
    for member in members:
        member_user_id = int(member["user_id"])
        record = by_user.get(member_user_id)
        raw_profile = getattr(record, "risk_profile", None) if record else None
        profile = str(raw_profile).strip().upper() if raw_profile is not None else None
        if profile is None or profile == "":
            missing.append(member_user_id)
            profile = None
        elif profile not in VALID_PROFILES:
            inconsistent.append(member_user_id)
        else:
            known.append(profile)
        rows.append(
            {
                "user_id": member_user_id,
                "full_name": member.get("full_name"),
                "profile": profile,
                "updated_at": getattr(record, "updated_at", None) if record else None,
            }
        )

    if inconsistent:
        status = "INCONSISTENT"
        effective = None
    elif missing:
        status = "MISSING"
        effective = None
    else:
        effective = min(known, key=lambda value: PROFILE_ORDER[value])
        status = "COMPLETE" if len(set(known)) == 1 else "MIXED"
    return {
        "status": status,
        "effective_profile": effective,
        # The canonical financial profile currently has no investment-horizon
        # field. Keep the absence explicit so the orchestrator can limit the
        # decision instead of silently assuming a long horizon.
        "investment_horizon": None,
        "members": rows,
        "missing_member_user_ids": missing,
        "inconsistent_member_user_ids": inconsistent,
        "profile_diversity": sorted(set(known), key=lambda value: PROFILE_ORDER[value]),
        "source": "financial_profiles.risk_profile",
    }


async def load_portfolio_context(
    session: AsyncSession,
    *,
    normalized_inputs: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe frozen owned_assets; absence remains UNKNOWN, never zero."""

    assets = [
        dict(item)
        for item in list(normalized_inputs.get("assets") or [])
        if item.get("status") == "ACTIVE" and item.get("asset_class") == "INVESTMENTS"
    ]
    if not assets:
        return {
            "status": "UNKNOWN",
            "positions": [],
            "total_known_value": None,
            "exposure_by_market": {},
            "concentration": [],
            "missing_information": ["owned_assets.investments"],
            "source": "financial_state.normalized_inputs.assets",
        }

    catalog_ids = sorted(
        {
            int(item["asset_catalog_id"])
            for item in assets
            if item.get("asset_catalog_id") is not None
        }
    )
    catalog_by_id: dict[int, AssetCatalog] = {}
    if catalog_ids:
        result = await session.execute(
            select(AssetCatalog).where(AssetCatalog.id.in_(catalog_ids))
        )
        catalog_by_id = {int(item.id): item for item in result.scalars().all()}

    positions: list[dict[str, Any]] = []
    missing: list[str] = []
    exposure: dict[str, Decimal] = {}
    total = Decimal("0.00")
    comparable_value_count = 0
    for item in assets:
        asset_id = int(item["id"])
        catalog_id = item.get("asset_catalog_id")
        catalog = catalog_by_id.get(int(catalog_id)) if catalog_id is not None else None
        value = item.get("current_value")
        currency = item.get("currency")
        market = getattr(catalog, "market", None)
        ticker = getattr(catalog, "ticker", None)
        if value is None:
            missing.append(f"owned_assets.{asset_id}.current_value")
        if currency is None:
            missing.append(f"owned_assets.{asset_id}.currency")
        elif value is not None and str(currency).upper() != SETTLEMENT_CURRENCY:
            missing.append(
                f"owned_assets.{asset_id}.currency_conversion_missing"
            )
        if catalog_id is None:
            missing.append(f"owned_assets.{asset_id}.asset_catalog_id")
        elif catalog is None:
            missing.append(f"owned_assets.{asset_id}.asset_catalog")
        if value is not None and str(currency).upper() == SETTLEMENT_CURRENCY:
            known_value = _money(value)
            total += known_value
            comparable_value_count += 1
            if market:
                exposure[market] = exposure.get(market, Decimal("0.00")) + known_value
        positions.append(
            {
                "owned_asset_id": asset_id,
                "asset_catalog_id": catalog_id,
                "ticker": ticker,
                "market": market,
                "name": item.get("name") or getattr(catalog, "name", None),
                "ownership_scope": item.get("ownership_scope"),
                "user_id": item.get("user_id"),
                "current_value": _money(value) if value is not None else None,
                "currency": str(currency).upper() if currency else None,
                "value_as_of": item.get("value_as_of"),
            }
        )

    concentration = []
    if total > 0:
        concentration = [
            {
                "market": market,
                "amount": amount,
                "percentage": (amount / total * Decimal("100")).quantize(
                    Decimal("0.01")
                ),
            }
            for market, amount in sorted(exposure.items())
        ]
    return {
        "status": "PARTIAL" if missing else "COMPLETE",
        "positions": positions,
        # A real BRL zero remains zero. If no position can be expressed safely
        # in the settlement currency, keep the aggregate unknown instead.
        "total_known_value": total if comparable_value_count else None,
        "exposure_by_market": exposure,
        "concentration": concentration,
        "missing_information": missing,
        "source": "financial_state.normalized_inputs.assets",
    }


async def _latest_common_market_date(
    session: AsyncSession,
    *,
    market: str,
):
    result = await session.execute(
        select(func.max(AssetScore.date))
        .join(
            AssetRecommendationGuardrail,
            and_(
                AssetRecommendationGuardrail.ticker == AssetScore.ticker,
                AssetRecommendationGuardrail.market == AssetScore.market,
                AssetRecommendationGuardrail.date == AssetScore.date,
                AssetRecommendationGuardrail.source == GUARDRAIL_SOURCE,
            ),
        )
        .where(AssetScore.market == market, AssetScore.source == SCORE_SOURCE)
    )
    return result.scalar_one_or_none()


async def load_market_context(
    session: AsyncSession,
    *,
    investment_budget: Decimal,
    profile: str | None,
    captured_at: datetime | None = None,
    limit_per_market: int = 20,
) -> dict[str, Any]:
    """Build a strict score+guardrail snapshot using canonical intelligence services.

    A score is never promoted when its exact ticker/date/source guardrail is absent.
    This adapter is read-only: Budget Advisor persistence is intentionally bypassed.
    """

    captured_at = captured_at or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    profile_value = str(profile).upper() if profile is not None else None
    if profile_value not in VALID_PROFILES:
        return {
            "captured_at": captured_at,
            "status": "BLOCKED",
            "markets": [],
            "candidates": [],
            "partial_failures": [],
            "missing_information": ["financial_profiles.risk_profile"],
            "sources": {
                "score": SCORE_SOURCE,
                "guardrail": GUARDRAIL_SOURCE,
                "trend": TREND_SOURCE,
            },
        }

    budget = _money(investment_budget)
    market_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    missing: list[str] = []
    failures: list[dict[str, str]] = []
    for market in SUPPORTED_MARKETS:
        try:
            data_date = await _latest_common_market_date(session, market=market)
            if data_date is None:
                missing.append(f"market.{market}.score_guardrail_snapshot")
                market_rows.append(
                    {
                        "market": market,
                        "label": MARKET_LABELS[market],
                        "status": "UNKNOWN",
                        "data_timestamp": None,
                        "freshness_status": "UNKNOWN",
                        "candidate_count": 0,
                    }
                )
                continue

            data_timestamp = datetime.combine(data_date, time.min, tzinfo=timezone.utc)
            age_days = max((captured_at.date() - data_date).days, 0)
            freshness = "FRESH" if age_days <= MARKET_FRESHNESS_DAYS else "STALE"
            score_result = await session.execute(
                select(AssetScore)
                .where(
                    AssetScore.market == market,
                    AssetScore.date == data_date,
                    AssetScore.source == SCORE_SOURCE,
                    AssetScore.price > 0,
                    AssetScore.score_total > 0,
                )
                .order_by(AssetScore.score_total.desc(), AssetScore.ticker.asc())
                .limit(max(limit_per_market * 8, 100))
            )
            scores = list(score_result.scalars().all())
            guardrail_result = await session.execute(
                select(AssetRecommendationGuardrail).where(
                    AssetRecommendationGuardrail.market == market,
                    AssetRecommendationGuardrail.date == data_date,
                    AssetRecommendationGuardrail.source == GUARDRAIL_SOURCE,
                )
            )
            guardrails = {
                item.ticker.upper(): item for item in guardrail_result.scalars().all()
            }
            # Strictly discard scores without an exact same-date guardrail.
            strict_scores = [
                item for item in scores if item.ticker.upper() in guardrails
            ]
            score_by_ticker = {item.ticker.upper(): item for item in strict_scores}

            catalog_result = await session.execute(
                select(AssetCatalog).where(
                    AssetCatalog.market == market,
                    AssetCatalog.ticker.in_(
                        [item.ticker for item in strict_scores]
                    ),
                )
            )
            catalogs = {
                item.ticker.upper(): item for item in catalog_result.scalars().all()
            }

            trend_result = await session.execute(
                select(AssetTrendSignal).where(
                    AssetTrendSignal.market == market,
                    AssetTrendSignal.date == data_date,
                    AssetTrendSignal.source == TREND_SOURCE,
                )
            )
            trends = {item.ticker.upper(): item for item in trend_result.scalars().all()}
            items = (
                build_budget_items(
                    strict_scores,
                    budget=budget,
                    limit=limit_per_market,
                    guardrails=guardrails,
                    include_warnings=True,
                    profile=profile_value,
                    trend_signals=trends,
                )
                if budget > 0
                else []
            )
            market_candidates: list[dict[str, Any]] = []
            for rank, item in enumerate(items, start=1):
                ticker_key = item.ticker.upper()
                score_record = score_by_ticker[ticker_key]
                guardrail_record = guardrails[ticker_key]
                trend_record = trends.get(ticker_key)
                catalog_record = catalogs.get(ticker_key)
                explanation = enrich_item_with_explanation(
                    item,
                    budget=budget,
                    summary=rank > 1,
                    context={
                        "budget": budget,
                        "market": market,
                        "profile": profile_value,
                        "recommendation_rank": rank,
                        "total_candidates": len(items),
                        "alternatives": [
                            other for other in items if other.ticker != item.ticker
                        ],
                    },
                )
                row = {
                    "asset_id": getattr(catalog_record, "id", None),
                    "asset_name": getattr(catalog_record, "name", None),
                    "symbol": item.ticker,
                    "ticker": item.ticker,
                    "asset_class": market,
                    "market": market,
                    "rank": rank,
                    "price_reference": item.price,
                    "quantity_candidate": item.quantity_possible,
                    "capital_required": item.invested_amount,
                    "recommendation_score": item.recommendation_score,
                    "score_total": item.score_total,
                    # Preserve the nullable canonical value. Budget Advisor
                    # normalizes missing subscores internally, but A4 must not
                    # reinterpret an absent liquidity score as a real zero.
                    "liquidity_score": score_record.score_liquidity,
                    "profile_score": item.profile_score,
                    "risk_level": item.risk_level,
                    "guardrail_status": item.status,
                    "guardrail_reasons": item.reasons_json or {},
                    "trend_label": item.trend_label,
                    "momentum_score": item.momentum_score,
                    "confidence": explanation.get("confidence_score"),
                    "reasons": explanation.get("why_recommended", []),
                    "warnings": explanation.get("attention_points", []),
                    "explanation": explanation,
                    "data_timestamp": data_timestamp,
                    "freshness_status": freshness,
                    "score_id": score_record.id,
                    "score_source": SCORE_SOURCE,
                    "score_calculated_at": score_record.calculated_at,
                    "score_metadata": score_record.metadata_json or {},
                    "guardrail_id": guardrail_record.id,
                    "guardrail_source": GUARDRAIL_SOURCE,
                    "guardrail_calculated_at": guardrail_record.calculated_at,
                    "trend_id": getattr(trend_record, "id", None),
                    "trend_source": TREND_SOURCE if trend_record is not None else None,
                    "trend_calculated_at": getattr(
                        trend_record, "calculated_at", None
                    ),
                    "trend_metadata": getattr(
                        trend_record, "metadata_json", None
                    )
                    or {},
                    "price_source": SCORE_SOURCE,
                }
                market_candidates.append(row)
                candidates.append(row)
            blocked_scores = [
                score
                for score in strict_scores
                if str(guardrails[score.ticker.upper()].status).upper() == "BLOCKED"
            ][: min(limit_per_market, 5)]
            for score in blocked_scores:
                ticker_key = score.ticker.upper()
                guardrail_record = guardrails[ticker_key]
                trend_record = trends.get(ticker_key)
                catalog_record = catalogs.get(ticker_key)
                blocked_row = {
                    "asset_id": getattr(catalog_record, "id", None),
                    "asset_name": getattr(catalog_record, "name", None),
                    "symbol": score.ticker,
                    "ticker": score.ticker,
                    "asset_class": market,
                    "market": market,
                    "rank": None,
                    "price_reference": score.price,
                    "quantity_candidate": 0,
                    "capital_required": Decimal("0.00"),
                    "recommendation_score": None,
                    "score_total": score.score_total,
                    "liquidity_score": score.score_liquidity,
                    "profile_score": None,
                    "risk_level": guardrail_record.risk_level,
                    "guardrail_status": "BLOCKED",
                    "guardrail_reasons": guardrail_record.reasons_json or {},
                    "trend_label": getattr(trend_record, "trend_label", None),
                    "momentum_score": getattr(trend_record, "momentum_score", None),
                    "confidence": None,
                    "reasons": ["Bloqueado pelos guardrails canônicos."],
                    "warnings": list(
                        (guardrail_record.reasons_json or {}).get("blocked", [])
                    ),
                    "explanation": {},
                    "data_timestamp": data_timestamp,
                    "freshness_status": freshness,
                    "score_id": score.id,
                    "score_source": SCORE_SOURCE,
                    "score_calculated_at": score.calculated_at,
                    "score_metadata": score.metadata_json or {},
                    "guardrail_id": guardrail_record.id,
                    "guardrail_source": GUARDRAIL_SOURCE,
                    "guardrail_calculated_at": guardrail_record.calculated_at,
                    "trend_id": getattr(trend_record, "id", None),
                    "trend_source": TREND_SOURCE if trend_record is not None else None,
                    "trend_calculated_at": getattr(
                        trend_record, "calculated_at", None
                    ),
                    "trend_metadata": getattr(
                        trend_record, "metadata_json", None
                    )
                    or {},
                    "price_source": SCORE_SOURCE,
                }
                market_candidates.append(blocked_row)
                candidates.append(blocked_row)
            market_rows.append(
                {
                    "market": market,
                    "label": MARKET_LABELS[market],
                    "status": "AVAILABLE" if market_candidates else "NO_CANDIDATE",
                    "data_timestamp": data_timestamp,
                    "freshness_status": freshness,
                    "age_days": age_days,
                    "candidate_count": len(market_candidates),
                    "strict_score_count": len(strict_scores),
                    "missing_guardrail_count": len(scores) - len(strict_scores),
                }
            )
        except Exception as exc:  # failure isolation is part of this adapter contract
            failures.append({"market": market, "error": type(exc).__name__})
            market_rows.append(
                {
                    "market": market,
                    "label": MARKET_LABELS[market],
                    "status": "UNAVAILABLE",
                    "data_timestamp": None,
                    "freshness_status": "UNKNOWN",
                    "candidate_count": 0,
                }
            )

    available = sum(1 for item in market_rows if item["status"] == "AVAILABLE")
    return {
        "captured_at": captured_at,
        "status": "AVAILABLE" if available else "UNAVAILABLE",
        "markets": market_rows,
        "candidates": candidates,
        "partial_failures": failures,
        "missing_information": missing,
        "sources": {
            "score": SCORE_SOURCE,
            "guardrail": GUARDRAIL_SOURCE,
            "trend": TREND_SOURCE,
        },
    }
