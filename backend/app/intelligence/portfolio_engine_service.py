from __future__ import annotations
from backend.app.intelligence.schemas import AllocationItem, AllocationOut, PortfolioEngineOut, FinancialProfileOut

MAX_BY_RISK = {"conservative": {"crypto":0,"equities":8,"bdrs":5}, "moderate": {"crypto":5,"equities":18,"bdrs":10}, "aggressive": {"crypto":10,"equities":30,"bdrs":15}}
MIN_CASH = {"conservative": 20, "moderate": 10, "aggressive": 5}

class PortfolioEngineService:
    @staticmethod
    def build(*, profile: FinancialProfileOut | object, allocation: AllocationOut) -> PortfolioEngineOut:
        risk = getattr(profile, 'risk_profile', 'moderate') or 'moderate'
        caps = MAX_BY_RISK.get(risk, MAX_BY_RISK['moderate'])
        weights = {i.market: float(i.percentage) for i in allocation.suggested_allocation}
        actions=[]
        for market, cap in caps.items():
            if weights.get(market, 0) > cap:
                actions.append(f"Reduzir {market} para no máximo {cap}% pelo seu perfil.")
                excess=weights[market]-cap; weights[market]=cap; weights['fixed_income']=weights.get('fixed_income',0)+excess
        if weights.get('cash',0) < MIN_CASH.get(risk,10):
            need=MIN_CASH[risk]-weights.get('cash',0); weights['cash']=MIN_CASH[risk]; weights['fixed_income']=max(0, weights.get('fixed_income',0)-need); actions.append('Reforçar caixa/reserva antes de aumentar risco.')
        total=sum(weights.values()) or 1
        items=[AllocationItem(market=k, percentage=round(v/total*100,2), rationale='peso ajustado por diversificação, risco e liquidez') for k,v in weights.items() if v>0]
        concentration=max([i.percentage for i in items] or [100])
        diversification=max(0, min(100, 120-concentration))
        if not actions: actions.append('Carteira sugerida dentro dos limites básicos de risco e diversificação.')
        return PortfolioEngineOut(allocation=items, risk_controls={'max_position_pct': round(concentration,2), 'min_cash_pct': MIN_CASH.get(risk,10), 'profile': risk}, rebalance_actions=actions, diversification_score=round(diversification,2), user_summary='Carteira montada para equilibrar meta, liquidez, diversificação e perfil de risco.')
