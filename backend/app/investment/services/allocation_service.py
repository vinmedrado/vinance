from __future__ import annotations

from typing import Any

from backend.app.investment.portfolio_allocator import PortfolioAllocator


def generate_allocation(
    *,
    perfil_risco: str | None,
    renda: float,
    despesas: float,
    reserva: float,
    objetivos: list[dict[str, Any]] | None = None,
    capital: float = 0.0,
    parcela_divida_mensal: float = 0.0,
    contexto_mercado: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return PortfolioAllocator().allocate(
        capital=capital,
        profile=perfil_risco,
        monthly_income=renda,
        monthly_expenses=despesas,
        emergency_reserve=reserva,
        monthly_debt_payment=parcela_divida_mensal,
        goals=objetivos or [],
        market_context=contexto_mercado or {},
    )
