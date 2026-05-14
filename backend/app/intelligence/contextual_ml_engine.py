from __future__ import annotations
from statistics import mean, pstdev
from backend.app.intelligence.schemas import ContextualMLAssetIn, ContextualMLAssetOut

RISK_WEIGHT = {'conservative': 1.35, 'moderate': 1.0, 'aggressive': 0.7}

class ContextualMLEngine:
    @staticmethod
    def score_assets(assets: list[ContextualMLAssetIn], *, risk_profile: str='moderate') -> list[ContextualMLAssetOut]:
        out=[]; penalty=RISK_WEIGHT.get(risk_profile,1.0)
        for a in assets:
            rets=a.returns or [0.004,0.006,0.003,0.005]
            avg=mean(rets); vol=pstdev(rets) if len(rets)>1 else 0.01
            trend='positivo' if avg>0.004 else 'neutro' if avg>=0 else 'negativo'
            regime='volatilidade alta' if vol>0.08 else 'volatilidade normal'
            quality=float(a.quality if a.quality is not None else 0.6)
            liq=float(a.liquidity if a.liquidity is not None else 0.6)
            dividend=float(a.dividend_yield if a.dividend_yield is not None else 0.0)
            raw=50 + avg*850 + quality*18 + liq*12 + min(dividend*120,8) - vol*100*penalty
            score=max(0,min(100,raw))
            fit='alta aderência' if score>=72 else 'aderência moderada' if score>=50 else 'baixa aderência'
            risk='risco elevado' if vol*penalty>0.09 else 'risco moderado' if vol*penalty>0.04 else 'risco controlado'
            out.append(ContextualMLAssetOut(symbol=a.symbol, market=a.market, contextual_score=round(score,2), regime=regime, risk_adjusted_label=risk, user_fit=fit, explanation=f"Score considera tendência {trend}, liquidez, qualidade e compatibilidade com o perfil {risk_profile}."))
        return sorted(out, key=lambda x: x.contextual_score, reverse=True)
