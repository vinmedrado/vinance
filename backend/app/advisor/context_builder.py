from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial.service import get_financial_profile
from backend.app.intelligence.service import build_recommendation_base

MAX_TOP_ASSETS_PER_CLASS = 3


def _safe_decimal(value: Any) -> float | int | str | None:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _compact_allocation(allocation: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "asset_class": item.get("asset_class"),
            "percentage": _safe_decimal(item.get("percentage")),
            "amount": _safe_decimal(item.get("amount")),
        }
        for item in allocation[:8]
    ]


def _compact_top_assets(classes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group in classes[:8]:
        asset_class = group.get("asset_class")
        result[str(asset_class)] = [
            {
                "ticker": asset.get("ticker"),
                "name": asset.get("name"),
                "score": asset.get("score"),
                "missing_fields": asset.get("missing_fields", [])[:5],
            }
            for asset in group.get("assets", [])[:MAX_TOP_ASSETS_PER_CLASS]
        ]
    return result


async def build_advisor_context(session: AsyncSession, *, user_id: int) -> dict[str, Any]:
    context: dict[str, Any] = {
        "financial": None,
        "allocation": [],
        "top_assets_by_class": {},
        "warnings": [],
        "context_available": False,
    }

    profile = await get_financial_profile(session, user_id=user_id)
    if profile is None:
        context["warnings"].append("Perfil financeiro ainda não cadastrado; contexto financeiro limitado.")
        return context

    try:
        recommendation = await build_recommendation_base(session, user_id=user_id)
    except Exception as exc:
        context["warnings"].append(f"Contexto financeiro/mercado indisponível: {exc}")
        return context

    context["financial"] = {
        "financial_score": recommendation.get("financial_score"),
        "investment_capacity": _safe_decimal(recommendation.get("investment_capacity")),
        "adjusted_risk_profile": recommendation.get("adjusted_risk_profile"),
    }
    context["allocation"] = _compact_allocation(recommendation.get("allocation", []))
    context["top_assets_by_class"] = _compact_top_assets(recommendation.get("recommendations_by_class", []))
    context["warnings"] = list(recommendation.get("warnings", []))[:8]
    context["methodology"] = list(recommendation.get("methodology", []))[:5]
    context["context_available"] = True
    return context
