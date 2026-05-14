from __future__ import annotations
from backend.app.intelligence.schemas import AllocationOut, RiskEngineOut

VOL = {'cash':1,'fixed_income':4,'etfs':13,'fiis':12,'equities':21,'bdrs':19,'crypto':48}
LIQ = {'cash':95,'fixed_income':80,'etfs':85,'fiis':70,'equities':78,'bdrs':70,'crypto':65}

class RiskEngineService:
    @staticmethod
    def assess(allocation: AllocationOut, *, risk_profile: str='moderate') -> RiskEngineOut:
        weights={i.market:i.percentage for i in allocation.suggested_allocation}
        concentration=max(weights.values() or [100])
        vol=sum(weights.get(k,0)*VOL.get(k,12)/100 for k in weights)
        liq=sum(weights.get(k,0)*LIQ.get(k,70)/100 for k in weights)
        drawdown=vol*1.35
        alerts=[]
        if concentration>45: alerts.append('Existe concentração relevante em um único mercado.')
        if weights.get('crypto',0)>10: alerts.append('Cripto acima de 10% pode elevar bastante a oscilação da carteira.')
        if liq<70: alerts.append('A liquidez projetada pode ser baixa para emergências.')
        label='baixo' if vol<8 and drawdown<12 else 'moderado' if vol<18 else 'elevado'
        return RiskEngineOut(risk_label=label, concentration_risk='elevado' if concentration>50 else 'moderado' if concentration>35 else 'baixo', liquidity_risk='elevado' if liq<55 else 'moderado' if liq<75 else 'baixo', expected_drawdown_pct=round(drawdown,2), volatility_estimate_pct=round(vol,2), alerts=alerts, user_summary=f'O risco estimado da carteira é {label}, considerando diversificação, liquidez e exposição por mercado.')
