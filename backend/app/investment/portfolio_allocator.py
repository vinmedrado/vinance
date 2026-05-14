from __future__ import annotations

from typing import Any

from backend.app.core.risk_profile import RiskProfile, normalize_risk_profile

BASE_ALLOCATIONS: dict[RiskProfile, dict[str, float]] = {
    RiskProfile.CONSERVADOR: {"caixa_reserva": 0.45, "renda_fixa": 0.35, "lci_lca": 0.10, "fiis": 0.05, "etfs": 0.05, "acoes": 0.00, "bdrs": 0.00, "cripto": 0.00},
    RiskProfile.MODERADO: {"caixa_reserva": 0.25, "renda_fixa": 0.25, "lci_lca": 0.10, "fiis": 0.15, "etfs": 0.10, "acoes": 0.10, "bdrs": 0.03, "cripto": 0.02},
    RiskProfile.ARROJADO: {"caixa_reserva": 0.15, "renda_fixa": 0.15, "lci_lca": 0.05, "fiis": 0.15, "etfs": 0.15, "acoes": 0.20, "bdrs": 0.10, "cripto": 0.05},
}


class PortfolioAllocator:
    """Motor oficial de alocação do FinanceOS.

    Todos os demais módulos devem delegar para este motor para evitar duplicidade.
    A alocação é por classe; ativos de classes diferentes nunca entram em ranking único.
    """

    def allocate(
        self,
        *,
        capital: float = 0.0,
        profile: str | RiskProfile | None = None,
        monthly_income: float = 0.0,
        monthly_expenses: float = 0.0,
        emergency_reserve: float = 0.0,
        monthly_debt_payment: float = 0.0,
        goals: list[dict[str, Any]] | None = None,
        market_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        risk_profile = normalize_risk_profile(profile)
        base = BASE_ALLOCATIONS[risk_profile].copy()
        income = max(float(monthly_income or 0), 0.0)
        expenses = max(float(monthly_expenses or 0), 0.0)
        reserve = max(float(emergency_reserve or 0), 0.0)
        debt = max(float(monthly_debt_payment or 0), 0.0)
        reserve_target = expenses * 6
        reserve_gap = max(reserve_target - reserve, 0.0)
        reserve_months = reserve / expenses if expenses > 0 else 0.0
        commitment = (expenses + debt) / income if income > 0 else 1.0
        explanations: list[str] = []

        if reserve_gap > 0:
            shift = 0.25 if reserve_months < 3 else 0.12
            self._shift_to(base, from_keys=("acoes", "bdrs", "cripto", "fiis", "etfs"), to_key="caixa_reserva", amount=shift)
            explanations.append("A reserva de emergência ainda não cobre 6 meses; a carteira prioriza liquidez antes de risco.")

        if commitment >= 0.75:
            self._shift_to(base, from_keys=("cripto", "bdrs", "acoes"), to_key="renda_fixa", amount=0.25)
            explanations.append("A renda está muito comprometida; o FinanceOS reduz volatilidade e aumenta renda fixa.")
        elif commitment >= 0.60:
            self._shift_to(base, from_keys=("cripto", "bdrs"), to_key="renda_fixa", amount=0.10)
            explanations.append("Há comprometimento relevante da renda; ativos de risco ficam limitados.")

        if goals:
            short_goals = [g for g in goals if str(g.get("prazo_tipo", "")).lower() in {"curto", "curto_prazo", "12m"}]
            if short_goals:
                self._shift_to(base, from_keys=("acoes", "bdrs", "cripto"), to_key="renda_fixa", amount=0.10)
                explanations.append("Existem objetivos de curto prazo; por isso o alocador evita oscilações fortes.")

        if market_context and (market_context.get("macro_stress") or 0) >= 0.7:
            self._shift_to(base, from_keys=("acoes", "bdrs", "cripto"), to_key="caixa_reserva", amount=0.08)
            explanations.append("O contexto de mercado está mais estressado; a sugestão reduz risco tático.")

        normalized = self._normalize(base)
        amount_capital = float(capital or 0)
        allocation = [
            {"asset_class": key, "percent": round(value, 4), "amount": round(amount_capital * value, 2)}
            for key, value in normalized.items()
        ]
        if not explanations:
            explanations.append("A distribuição segue o perfil de risco, mantendo diversificação e sem comparar classes diferentes.")
        return {
            "risk_profile": risk_profile.value,
            "capital": amount_capital,
            "allocation": allocation,
            "allocation_by_class": normalized,
            "reserve_target": round(reserve_target, 2),
            "reserve_gap": round(reserve_gap, 2),
            "reserve_months": round(reserve_months, 2),
            "income_commitment_pct": round(commitment, 4),
            "explanation": explanations,
            "rules": [
                "Não existe ranking único entre ações, FIIs, ETFs, cripto e renda fixa.",
                "A reserva de emergência vem antes de buscar rentabilidade.",
                "Dívida e financiamento reduzem a exposição recomendada a volatilidade.",
            ],
            "disclaimer": "Planejamento educacional; não promete rentabilidade e não substitui consultoria regulada.",
        }

    @staticmethod
    def _normalize(values: dict[str, float]) -> dict[str, float]:
        positive = {k: max(float(v), 0.0) for k, v in values.items()}
        total = sum(positive.values()) or 1.0
        return {k: v / total for k, v in positive.items()}

    @staticmethod
    def _shift_to(values: dict[str, float], *, from_keys: tuple[str, ...], to_key: str, amount: float) -> None:
        per_key = amount / max(len(from_keys), 1)
        moved = 0.0
        for key in from_keys:
            cut = min(values.get(key, 0.0), per_key)
            values[key] = values.get(key, 0.0) - cut
            moved += cut
        values[to_key] = values.get(to_key, 0.0) + moved


def allocate(**kwargs: Any) -> dict[str, Any]:
    return PortfolioAllocator().allocate(**kwargs)
