from __future__ import annotations
from backend.app.intelligence.schemas import AdvancedBacktestOut, HumanizedRecommendationOut, RiskEngineOut, FinancialGoalEngineOut

DISCLAIMER = 'O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.'

class HumanizedRecommendationEngine:
    @staticmethod
    def explain(*, goal: FinancialGoalEngineOut | None=None, backtest: AdvancedBacktestOut | None=None, risk: RiskEngineOut | None=None, monthly_contribution: float=0) -> HumanizedRecommendationOut:
        risk_label = risk.risk_label if risk else 'moderado'
        main = f'Seu perfil atual suporta uma carteira de risco {risk_label}, com foco em seguir a meta sem comprometer sua segurança financeira.'
        why=['A sugestão combina sua capacidade de aporte, prazo e tolerância a risco.', 'O sistema prioriza diversificação e reserva antes de aumentar exposição a ativos voláteis.']
        risks=[]
        if risk and risk.alerts: risks.extend(risk.alerts)
        else: risks.append('Mesmo uma carteira equilibrada pode oscilar e ter períodos abaixo do esperado.')
        goal_impact = goal.plain_language_summary if goal else 'A estratégia deve ser revisada sempre que renda, despesas ou prazo mudarem.'
        contribution_impact = f'Aumentar o aporte acima de R$ {monthly_contribution:,.2f}/mês tende a reduzir a dependência de retornos altos.'.replace(',', 'X').replace('.', ',').replace('X','.')
        deadline_impact = 'Diminuir o prazo exige aporte maior ou mais risco; alongar o prazo costuma deixar a meta mais saudável.'
        comparison = 'Comparada a uma estratégia simples só em caixa, a carteira sugerida busca mais crescimento, mantendo reserva de segurança.'
        return HumanizedRecommendationOut(main_recommendation=main, why=why, risks=risks, goal_impact=goal_impact, contribution_impact=contribution_impact, deadline_impact=deadline_impact, simple_strategy_comparison=comparison, disclaimer=DISCLAIMER)
