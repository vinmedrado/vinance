from __future__ import annotations

from .base import AssetClassAnalysis, max_drawdown, pct_return, safe_round, volatility


class BDREngine:
    asset_class = "bdr"

    def analyze(self, symbol: str, prices: list[float], dividends: list[float] | None = None) -> dict:
        vol = volatility(prices)
        dd = max_drawdown(prices)
        risk = "medio"
        if (vol or 0) > 0.40 or (dd or 0) < -0.35:
            risk = "alto"
        elif (vol or 0) < 0.22 and (dd or 0) > -0.20:
            risk = "baixo"
        return AssetClassAnalysis(self.asset_class, symbol, {
            "historical_return": safe_round(pct_return(prices)),
            "volatility": safe_round(vol),
            "max_drawdown": safe_round(dd),
            "currency_risk": "exposição indireta ao dólar",
        }, risk, [
            "BDR foi analisado considerando volatilidade, drawdown e exposição internacional.",
            "O risco cambial pode ajudar na diversificação, mas aumenta a oscilação em reais.",
        ], "exposição internacional com risco cambial").as_dict()
