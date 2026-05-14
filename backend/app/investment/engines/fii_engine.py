from __future__ import annotations

from .base import AssetClassAnalysis, max_drawdown, pct_return, safe_round, volatility


class FIIEngine:
    asset_class = "fii"

    def analyze(self, symbol: str, prices: list[float], dividends: list[float]) -> dict:
        annual_dividends = sum(dividends[-12:]) if dividends else 0.0
        last_price = next((p for p in reversed(prices) if p and p > 0), 0.0)
        dy = annual_dividends / last_price if last_price > 0 else None
        vol = volatility(prices)
        dd = max_drawdown(prices)
        consistency = (len([d for d in dividends[-12:] if d and d > 0]) / 12) if dividends else 0.0
        risk = "baixo" if consistency >= 0.75 and (vol or 0) < 0.25 else "medio"
        if consistency < 0.40 or (vol or 0) > 0.45 or (dd or 0) < -0.35:
            risk = "alto"
        explanation = [
            "FII foi analisado por renda recorrente, consistência de dividendos e estabilidade de preço.",
            f"Consistência recente de dividendos: {consistency:.0%} dos últimos 12 registros.",
        ]
        if dy is not None:
            explanation.append(f"Dividend yield estimado pelos últimos registros: {dy:.2%}.")
        return AssetClassAnalysis(self.asset_class, symbol, {
            "dividend_yield_estimated": safe_round(dy),
            "dividend_consistency_12m": safe_round(consistency),
            "volatility": safe_round(vol),
            "max_drawdown": safe_round(dd),
            "historical_return": safe_round(pct_return(prices)),
        }, risk, explanation, "geração de renda e diversificação imobiliária").as_dict()
