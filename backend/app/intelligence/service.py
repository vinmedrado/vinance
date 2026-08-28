from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial.service import calculate_financial_diagnosis
from backend.app.intelligence.allocation import calculate_allocation as calculate_allocation_engine
from backend.app.intelligence.asset_scoring import rank_assets
from backend.app.market.service import (
    list_acoes_fundamentals,
    list_bdr_fundamentals,
    list_cripto_fundamentals,
    list_etf_fundamentals,
    list_fii_fundamentals,
    list_renda_fixa_produtos,
)

ASSET_CLASSES = ["renda_fixa", "fii", "acoes", "etf", "bdr", "cripto"]


async def get_financial_context(session: AsyncSession, *, user_id: int) -> dict:
    diagnosis = await calculate_financial_diagnosis(session, user_id=user_id)
    monthly_salary = Decimal(str(diagnosis.get("monthly_salary") or 0))
    total_expenses = Decimal(str(diagnosis.get("total_expenses_30d") or 0))
    reserve = Decimal(str(diagnosis.get("emergency_reserve") or 0))
    reserve_months = reserve / total_expenses if total_expenses > 0 else Decimal("0")
    return {
        "financial_score": int(diagnosis["score"]["score"]),
        "investment_capacity": Decimal(str(diagnosis["budget"]["investment_capacity"] or 0)),
        "risk_profile": diagnosis.get("risk_profile") or "conservative",
        "emergency_reserve_priority": bool(diagnosis["budget"].get("emergency_reserve_priority", False)),
        "high_risk_allowed": bool(diagnosis["budget"].get("high_risk_allowed", True)),
        "has_debt_default": bool(diagnosis.get("has_debt_default", False)),
        "emergency_reserve_months": reserve_months,
        "monthly_salary": monthly_salary,
    }


def calculate_allocation(**kwargs) -> dict:
    return calculate_allocation_engine(**kwargs)


async def _read_assets_by_class(session: AsyncSession) -> dict[str, list[Any]]:
    fiis, _ = await list_fii_fundamentals(session, limit=100)
    acoes, _ = await list_acoes_fundamentals(session, limit=100)
    etfs, _ = await list_etf_fundamentals(session, limit=100)
    bdrs, _ = await list_bdr_fundamentals(session, limit=100)
    criptos, _ = await list_cripto_fundamentals(session, limit=100)
    renda_fixa, _ = await list_renda_fixa_produtos(session, is_active=True)
    return {
        "renda_fixa": renda_fixa,
        "fii": fiis,
        "acoes": acoes,
        "etf": etfs,
        "bdr": bdrs,
        "cripto": criptos,
    }


def rank_assets_by_class(assets_by_class: dict[str, list[Any]], *, limit: int = 10) -> dict[str, list[dict]]:
    ranked: dict[str, list[dict]] = {}
    for asset_class in ASSET_CLASSES:
        ranked[asset_class] = rank_assets(asset_class, assets_by_class.get(asset_class, []), limit=limit)
    return ranked


async def build_recommendation_base(
    session: AsyncSession,
    *,
    user_id: int,
    amount: Decimal | None = None,
    risk_profile: str | None = None,
) -> dict:
    context = await get_financial_context(session, user_id=user_id)
    investment_capacity = Decimal(str(amount)) if amount is not None else context["investment_capacity"]
    selected_risk_profile = risk_profile or context["risk_profile"]

    allocation_result = calculate_allocation(
        investment_capacity=investment_capacity,
        risk_profile=selected_risk_profile,
        financial_score=context["financial_score"],
        emergency_reserve_priority=context["emergency_reserve_priority"],
        high_risk_allowed=context["high_risk_allowed"],
        has_debt_default=context["has_debt_default"],
        emergency_reserve_months=context["emergency_reserve_months"],
    )

    assets_by_class = await _read_assets_by_class(session)
    ranked_assets = rank_assets_by_class(assets_by_class)
    warnings = list(allocation_result["warnings"])

    recommendations_by_class = []
    for item in allocation_result["allocation"]:
        asset_class = item["asset_class"]
        assets = ranked_assets.get(asset_class, [])
        recommendations_by_class.append(
            {
                "asset_class": asset_class,
                "allocation_percentage": item["percentage"],
                "allocation_amount": item["amount"],
                "assets": assets,
                "message": None if assets else "dados de fundamentos ainda não disponíveis",
            }
        )

    if not any(ranked_assets.values()):
        warnings.append("dados de fundamentos ainda não disponíveis")

    return {
        "financial_score": context["financial_score"],
        "investment_capacity": investment_capacity,
        "adjusted_risk_profile": allocation_result["adjusted_risk_profile"],
        "allocation": allocation_result["allocation"],
        "recommendations_by_class": recommendations_by_class,
        "warnings": warnings,
        "methodology": [
            "Sugestão educacional baseada em diagnóstico financeiro, perfil de risco e orçamento disponível.",
            "Allocation por classe normalizada para fechar 100% após restrições financeiras.",
            "Ranking heurístico 0-100 por classe; dados ausentes recebem pontuação neutra documentada.",
            "Não há ML treinado, advisor de IA, backtest ou chamada externa nesta fase.",
        ],
    }
