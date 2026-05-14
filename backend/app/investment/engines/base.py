from __future__ import annotations

from typing import Any

from backend.app.core.finance_math import max_drawdown, pct_return, safe_round, volatility


def human_risk(level: str) -> str:
    return {
        "baixo": "baixo risco dentro desta classe",
        "medio": "risco moderado dentro desta classe",
        "alto": "alto risco dentro desta classe",
    }.get(level, level)


class AssetClassAnalysis:
    def __init__(self, asset_class: str, symbol: str, metrics: dict[str, Any], risk: str, explanation: list[str], role: str):
        self.asset_class = asset_class
        self.symbol = symbol
        self.metrics = metrics
        self.risk = risk
        self.explanation = explanation
        self.role = role

    def as_dict(self) -> dict[str, Any]:
        return {
            "asset_class": self.asset_class,
            "symbol": self.symbol,
            "risk": self.risk,
            "risk_text": human_risk(self.risk),
            "metrics": self.metrics,
            "explanation": self.explanation,
            "portfolio_role": self.role,
            "disclaimer": "Análise educacional, sem promessa de ganho e sem previsão de preço.",
        }
