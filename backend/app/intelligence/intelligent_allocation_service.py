from __future__ import annotations

from backend.app.intelligence.schemas import AllocationItem, AllocationOut, FinancialProfileOut

DEFAULT_ALLOCATIONS = {
    "conservative": {"cash": 25, "fixed_income": 45, "etfs": 20, "fiis": 10, "equities": 0, "bdrs": 0, "crypto": 0},
    "moderate": {"cash": 15, "fixed_income": 25, "etfs": 30, "fiis": 20, "equities": 7, "bdrs": 3, "crypto": 0},
    "aggressive": {"cash": 10, "fixed_income": 15, "etfs": 30, "fiis": 15, "equities": 18, "bdrs": 7, "crypto": 5},
}

MARKET_LABELS = {
    "cash": "caixa/reserva",
    "fixed_income": "renda fixa/CDI",
    "etfs": "ETFs",
    "fiis": "FIIs",
    "equities": "ações",
    "bdrs": "BDRs",
    "crypto": "cripto",
}

RATIONALES = {
    "cash": "mantém liquidez e reduz risco de precisar vender investimentos em momento ruim",
    "fixed_income": "dá previsibilidade e ajuda a proteger a reserva e metas de curto/médio prazo",
    "etfs": "oferece diversificação simples sem exigir escolha manual de muitas ações",
    "fiis": "pode gerar renda recorrente, respeitando o limite de risco do perfil",
    "equities": "aumenta potencial de crescimento, mas com oscilação controlada pela alocação",
    "bdrs": "adiciona exposição internacional de forma limitada e diversificada",
    "crypto": "entra apenas como parcela pequena por ser mais volátil",
}


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(v for v in weights.values() if v > 0)
    if total <= 0:
        return {"cash": 100.0}
    return {k: round(v / total * 100, 2) for k, v in weights.items() if v > 0}


class IntelligentAllocationService:
    @staticmethod
    def suggest(profile: FinancialProfileOut | object) -> AllocationOut:
        risk = getattr(profile, "risk_profile", "moderate") or "moderate"
        preferred = set(getattr(profile, "preferred_markets", []) or [])
        base = DEFAULT_ALLOCATIONS.get(risk, DEFAULT_ALLOCATIONS["moderate"]).copy()

        if preferred:
            # Mantém caixa/renda fixa para segurança, mas remove mercados não preferidos de risco.
            for market in list(base):
                if market not in {"cash", "fixed_income"} and market not in preferred:
                    base[market] = 0
        if getattr(profile, "liquidity_preference", "medium") == "high":
            base["cash"] = base.get("cash", 0) + 10
            base["fixed_income"] = base.get("fixed_income", 0) + 5
        if getattr(profile, "dividend_preference", "medium") == "high":
            base["fiis"] = base.get("fiis", 0) + 8
        if getattr(profile, "volatility_tolerance", "medium") == "low":
            base["crypto"] = 0
            base["equities"] = max(base.get("equities", 0) - 8, 0)
            base["fixed_income"] = base.get("fixed_income", 0) + 8

        normalized = _normalize(base)
        items = [
            AllocationItem(market=MARKET_LABELS.get(market, market), percentage=pct, rationale=RATIONALES.get(market, "aderente ao perfil informado"))
            for market, pct in sorted(normalized.items(), key=lambda kv: kv[1], reverse=True)
        ]
        estimated_risk = {"conservative": "baixo", "moderate": "médio", "aggressive": "alto"}.get(risk, "médio")
        goal_compatibility = "compatível" if risk != "aggressive" or getattr(profile, "investment_horizon", "medium_term") != "short_term" else "exige cuidado pelo prazo"
        summary = f"Carteira {risk.replace('_', ' ')} sugerida com foco em {items[0].market if items else 'reserva'}, mantendo diversificação e liquidez."
        return AllocationOut(risk_profile=risk, suggested_allocation=items, estimated_risk=estimated_risk, goal_compatibility=goal_compatibility, plain_language_summary=summary)
