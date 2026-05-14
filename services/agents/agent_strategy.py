
from __future__ import annotations
from typing import Any
from services.agents.base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    name = "strategy"
    description = "Avalia estratégia e resultados sem alterar lógica."

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        strategy = context.get("strategy") or {}
        bt = context.get("backtest") or {}

        def _float(value):
            try:
                return float(value) if value is not None else None
            except Exception:
                return None

        def _int(value):
            try:
                return int(value) if value is not None else None
            except Exception:
                return None

        total_return = _float(bt.get("total_return"))
        sharpe = _float(bt.get("sharpe_ratio"))
        trades = _int(bt.get("total_trades"))

        insights = []
        recommendations = [
            "Use esta avaliação como leitura, não como alteração automática da estratégia.",
            "Valide o resultado em períodos diferentes antes de confiar operacionalmente.",
        ]

        status = "ok"
        score = 70

        if total_return is None:
            status = "warning"
            insights.append(self.make_insight("medium", "Retorno indisponível", "Não há retorno total recente para avaliar a estratégia.", "Rode backtest ou relatório de estratégia."))
            score -= 10
        elif total_return < 0:
            status = "warning"
            insights.append(self.make_insight("high", "Retorno negativo", f"Retorno total observado: {total_return:.2%}.", "Revise filtros, universo e período antes de usar o resultado."))
            score -= 30
        else:
            insights.append(self.make_insight("low", "Retorno positivo", f"Retorno total observado: {total_return:.2%}.", "Compare com benchmark e risco assumido."))

        if sharpe is not None:
            if sharpe < 0.5:
                status = "warning"
                insights.append(self.make_insight("medium", "Sharpe baixo", f"Sharpe observado: {sharpe:.2f}.", "Avalie se o retorno compensa a volatilidade."))
                score -= 20
            elif sharpe >= 1:
                insights.append(self.make_insight("low", "Sharpe interessante", f"Sharpe observado: {sharpe:.2f}.", "Verifique robustez em outras janelas."))

        if trades is not None and trades < 10:
            status = "warning"
            insights.append(self.make_insight("medium", "Amostra pequena", f"Apenas {trades} trade(s) no backtest recente.", "Não tire conclusão forte com baixa amostra."))
            score -= 15

        return {
            "agent": self.name,
            "status": status,
            "summary": "Avaliação interpretativa da estratégia sem alterar sua lógica.",
            "insights": insights,
            "recommendations": recommendations,
            "metrics_used": {
                "strategy_name": strategy.get("name") or "multi_factor",
                "total_return": total_return,
                "sharpe_ratio": sharpe,
                "total_trades": trades,
            },
            "score": max(0, min(100, score)),
        }
