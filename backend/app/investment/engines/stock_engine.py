from __future__ import annotations

from .base import AssetClassAnalysis, max_drawdown, pct_return, safe_round, volatility


class StockEngine:
    asset_class = "acao"

    def analyze(self, symbol: str, prices: list[float], dividends: list[float] | None = None) -> dict:
        vol = volatility(prices)
        dd = max_drawdown(prices)
        ret = pct_return(prices)
        risk = "baixo" if (vol or 0) < 0.22 and (dd or 0) > -0.20 else "medio"
        if (vol or 0) > 0.45 or (dd or 0) < -0.40:
            risk = "alto"
        return AssetClassAnalysis(self.asset_class, symbol, {
            "historical_return": safe_round(ret),
            "volatility": safe_round(vol),
            "max_drawdown": safe_round(dd),
        }, risk, [
            "Ação foi analisada por retorno histórico, volatilidade e queda máxima.",
            "Esse motor não compara a ação com FIIs, ETFs ou renda fixa; a análise é apenas dentro da classe ações.",
        ], "crescimento de capital com maior oscilação").as_dict()
