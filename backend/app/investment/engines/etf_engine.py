from __future__ import annotations

from .base import AssetClassAnalysis, max_drawdown, pct_return, safe_round, volatility


class ETFEngine:
    asset_class = "etf"

    def analyze(self, symbol: str, prices: list[float], dividends: list[float] | None = None) -> dict:
        vol = volatility(prices)
        dd = max_drawdown(prices)
        risk = "baixo" if (vol or 0) < 0.18 and (dd or 0) > -0.18 else "medio"
        if (vol or 0) > 0.35 or (dd or 0) < -0.35:
            risk = "alto"
        return AssetClassAnalysis(self.asset_class, symbol, {
            "historical_return": safe_round(pct_return(prices)),
            "volatility": safe_round(vol),
            "max_drawdown": safe_round(dd),
            "diversification_score": 0.8,
        }, risk, [
            "ETF foi avaliado como instrumento de diversificação, com foco em volatilidade e drawdown.",
            "A análise considera o papel do ETF na carteira, não um ranking contra ativos de outras classes.",
        ], "diversificação simples e exposição ampla").as_dict()
