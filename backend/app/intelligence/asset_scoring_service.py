from __future__ import annotations

from backend.app.intelligence.schemas import AssetScoreIn, AssetScoreOut


def _bounded(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _risk_from_vol(vol: float | None, market: str) -> str:
    if market == "crypto":
        return "alto"
    v = float(vol or 0.35)
    if v >= 0.45:
        return "alto"
    if v >= 0.22:
        return "médio"
    return "baixo"


class AssetScoringService:
    """Scoring contextual. Não tenta prever preço de amanhã; ranqueia aderência e qualidade."""

    @staticmethod
    def score_asset(asset: AssetScoreIn, *, risk_profile: str = "moderate") -> AssetScoreOut:
        volatility = float(asset.volatility if asset.volatility is not None else 0.25)
        liquidity = float(asset.liquidity if asset.liquidity is not None else 0.6)
        trend = float(asset.trend if asset.trend is not None else 0.5)
        drawdown = abs(float(asset.drawdown if asset.drawdown is not None else 0.2))
        quality = float(asset.quality if asset.quality is not None else 0.6)
        consistency = float(asset.consistency if asset.consistency is not None else 0.55)

        score = 50.0
        score += _bounded(liquidity * 20, 0, 20)
        score += _bounded(quality * 15, 0, 15)
        score += _bounded(consistency * 10, 0, 10)
        score += _bounded(trend * 10, 0, 10)
        score -= _bounded(volatility * 25, 0, 25)
        score -= _bounded(drawdown * 20, 0, 20)

        if asset.market == "fiis":
            score += _bounded(float(asset.dividend_yield or 0) * 120, 0, 10)
            score -= _bounded(float(asset.vacancy or 0) * 20, 0, 10)
        if asset.market == "etfs":
            score -= _bounded(float(asset.tracking_error or 0) * 100, 0, 8)
        if asset.market == "crypto":
            score -= 12
        if risk_profile == "conservative" and asset.market in {"crypto", "equities", "bdrs"}:
            score -= 12
        if risk_profile == "aggressive" and asset.market in {"fixed_income", "cash"}:
            score -= 4

        score = round(_bounded(score), 2)
        risk = _risk_from_vol(asset.volatility, asset.market)
        if score >= 75:
            compatibility = "alta"
            context = "Boa aderência ao perfil informado, mantendo atenção ao risco do mercado."
        elif score >= 55:
            compatibility = "média"
            context = "Pode compor a carteira em proporção controlada."
        else:
            compatibility = "baixa"
            context = "Exige cautela ou dados melhores antes de entrar na sugestão principal."
        return AssetScoreOut(symbol=asset.symbol, market=asset.market, score=score, profile_compatibility=compatibility, risk=risk, recommendation_context=context)

    @classmethod
    def score_assets(cls, assets: list[AssetScoreIn], *, risk_profile: str = "moderate") -> list[AssetScoreOut]:
        return sorted([cls.score_asset(asset, risk_profile=risk_profile) for asset in assets], key=lambda item: item.score, reverse=True)
