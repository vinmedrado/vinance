
from __future__ import annotations
from typing import Any
from services.agents.base_agent import BaseAgent


class RiskAgent(BaseAgent):
    name = "risk"
    description = "Avalia risco com base em backtests, drawdown, volatilidade e Sharpe."

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        bt = context.get("backtest") or {}

        def _float(value):
            try:
                return float(value) if value is not None else None
            except Exception:
                return None

        sharpe = _float(bt.get("sharpe_ratio"))
        drawdown = _float(bt.get("max_drawdown"))
        volatility = _float(bt.get("volatility"))

        insights = []
        recommendations = [
            "Não aumente exposição sem validar drawdown e consistência fora da amostra.",
            "Compare risco contra benchmark e diferentes janelas temporais.",
        ]

        score = 75
        status = "ok"
        risk_level = "moderado"

        if sharpe is not None:
            if sharpe < 0.5:
                status = "warning"
                score -= 20
                insights.append(self.make_insight("medium", "Retorno ajustado ao risco fraco", f"Sharpe observado: {sharpe:.2f}.", "Busque melhorar consistência antes de elevar exposição."))
            else:
                insights.append(self.make_insight("low", "Sharpe aceitável", f"Sharpe observado: {sharpe:.2f}.", "Confirme em outras janelas."))

        if drawdown is not None:
            dd = abs(drawdown)
            if dd >= 0.25:
                status = "critical"
                risk_level = "alto"
                score -= 35
                insights.append(self.make_insight("high", "Drawdown elevado", f"Drawdown máximo observado: {dd:.2%}.", "Reduza exposição ou revise filtros antes de operar."))
            elif dd >= 0.15:
                status = "warning"
                score -= 15
                insights.append(self.make_insight("medium", "Drawdown relevante", f"Drawdown máximo observado: {dd:.2%}.", "Monitore risco de perda acumulada."))
            else:
                insights.append(self.make_insight("low", "Drawdown controlado", f"Drawdown máximo observado: {dd:.2%}.", "Ainda assim valide em cenário adverso."))

        if volatility is not None and abs(volatility) >= 0.30:
            status = "warning" if status != "critical" else status
            score -= 10
            insights.append(self.make_insight("medium", "Volatilidade alta", f"Volatilidade observada: {abs(volatility):.2%}.", "Avalie sizing e diversificação."))

        if score >= 80:
            risk_level = "baixo"
        elif score < 50:
            risk_level = "alto"

        return {
            "agent": self.name,
            "status": status,
            "summary": f"Risco estimado como {risk_level} pelas métricas disponíveis.",
            "insights": insights,
            "recommendations": recommendations,
            "metrics_used": {
                "sharpe_ratio": sharpe,
                "max_drawdown": drawdown,
                "volatility": volatility,
                "risk_level": risk_level,
            },
            "score": max(0, min(100, score)),
            "risk_level": risk_level,
        }
