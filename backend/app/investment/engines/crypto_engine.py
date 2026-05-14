from __future__ import annotations

from .base import AssetClassAnalysis, max_drawdown, pct_return, safe_round, volatility


class CryptoEngine:
    asset_class = "cripto"

    def analyze(self, symbol: str, prices: list[float], dividends: list[float] | None = None) -> dict:
        vol = volatility(prices)
        dd = max_drawdown(prices)
        risk = "alto"
        if (vol or 0) < 0.35 and (dd or 0) > -0.30:
            risk = "medio"
        return AssetClassAnalysis(self.asset_class, symbol, {
            "historical_return": safe_round(pct_return(prices)),
            "volatility": safe_round(vol),
            "max_drawdown": safe_round(dd),
            "liquidity_risk": "alto em cenários de estresse",
        }, risk, [
            "Cripto foi tratada como classe de alto risco por volatilidade e incerteza elevada.",
            "O FinanceOS limita cripto por perfil e reserva, sem prometer ganho ou prever preço.",
        ], "exposição alternativa de alto risco e baixa prioridade sem reserva completa").as_dict()
