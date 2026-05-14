from __future__ import annotations

from backend.app.intelligence.asset_scoring_service import AssetScoringService
from backend.app.intelligence.financial_capacity_service import FinancialCapacityService
from backend.app.intelligence.intelligent_allocation_service import IntelligentAllocationService
from backend.app.intelligence.personalized_backtest_service import DISCLAIMER, PersonalizedBacktestService
from backend.app.intelligence.schemas import AssetScoreIn, RecommendationOut


class InvestmentRecommendationService:
    @staticmethod
    def generate(*, profile, assets: list[AssetScoreIn] | None = None) -> RecommendationOut:
        capacity = FinancialCapacityService.calculate(
            monthly_income=getattr(profile, "monthly_income", 0),
            monthly_expenses=getattr(profile, "monthly_expenses", 0),
            available_to_invest=getattr(profile, "available_to_invest", None),
            emergency_reserve_months=getattr(profile, "emergency_reserve_months", 0),
            risk_profile=getattr(profile, "risk_profile", "moderate"),
        )
        allocation = IntelligentAllocationService.suggest(profile)
        backtest = PersonalizedBacktestService.simulate(profile=profile, allocation=allocation, capacity=capacity)
        scores = AssetScoringService.score_assets(assets or [], risk_profile=getattr(profile, "risk_profile", "moderate"))
        goal = getattr(profile, "financial_goal", None) or "sua meta financeira"
        contribution = capacity.monthly_contribution_capacity
        recommendation = (
            f"Com base na sua renda, despesas e meta de {goal}, o Vinance sugere investir cerca de "
            f"R$ {contribution:,.2f}/mês em uma carteira de risco {allocation.estimated_risk}, com diversificação por mercado."
        ).replace(",", "X").replace(".", ",").replace("X", ".")
        explanations = [
            capacity.plain_language_summary,
            allocation.plain_language_summary,
            "A estratégia evita depender de uma única classe de ativo e respeita sua tolerância a risco.",
            "A simulação usa cenários histórico-estatísticos para ajudar no planejamento, não para prometer resultado.",
        ] + capacity.alerts
        goal_estimate = (
            f"Chance estimada de atingir a meta no cenário base: {backtest.estimated_goal_success_chance_pct:.0f}%"
            if backtest.estimated_goal_success_chance_pct is not None else
            "Cadastre valor e data da meta para estimar a chance de alcançar o objetivo."
        )
        return RecommendationOut(
            recommendation=recommendation,
            recommended_monthly_contribution=contribution,
            suggested_allocation=allocation.suggested_allocation,
            risk=allocation.estimated_risk,
            goal_estimate=goal_estimate,
            benchmark_comparison=backtest.benchmark_comparison,
            scenarios=backtest.scenarios,
            explanations=explanations,
            asset_scores=scores,
            disclaimer=DISCLAIMER,
        )
