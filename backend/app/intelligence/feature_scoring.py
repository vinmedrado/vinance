from __future__ import annotations

from decimal import Decimal

from backend.app.intelligence.feature_pipeline.common import score_linear, weighted_score


def clamp_score(score: Decimal | float | int | None) -> Decimal:
    if score is None:
        return Decimal("50.000000")
    numeric = max(0.0, min(100.0, float(score)))
    return Decimal(str(round(numeric, 6)))


def score_fii_features(*, dy_trend_3m=None, pvp_zscore=None, vacancia_delta=None, momentum_30d=None, momentum_90d=None, volatilidade_30d=None, retorno_vs_ifix=None) -> Decimal:
    """FIIs: peso maior para valuation, dividendos sustentáveis e baixa vacância/volatilidade."""
    return weighted_score([
        (score_linear(dy_trend_3m, low=-2, high=2), 0.16),
        (score_linear(abs(float(pvp_zscore)) if pvp_zscore is not None else None, low=0, high=2.5, invert=True), 0.20),
        (score_linear(vacancia_delta, low=-5, high=5, invert=True), 0.14),
        (score_linear(momentum_30d, low=-15, high=15), 0.12),
        (score_linear(momentum_90d, low=-25, high=25), 0.12),
        (score_linear(volatilidade_30d, low=5, high=60, invert=True), 0.16),
        (score_linear(retorno_vs_ifix, low=-15, high=15), 0.10),
    ])


def score_acoes_features(*, pl_zscore=None, roe_trend_3m=None, momentum_30d=None, momentum_90d=None, momentum_252d=None, volatilidade_30d=None, volatilidade_90d=None, retorno_vs_ibov=None, volume_anomaly=None) -> Decimal:
    """Ações: combina valuation relativo, qualidade, momentum controlado, risco e liquidez."""
    return weighted_score([
        (score_linear(abs(float(pl_zscore)) if pl_zscore is not None else None, low=0, high=3, invert=True), 0.16),
        (score_linear(roe_trend_3m, low=-5, high=5), 0.14),
        (score_linear(momentum_30d, low=-20, high=20), 0.10),
        (score_linear(momentum_90d, low=-30, high=30), 0.12),
        (score_linear(momentum_252d, low=-50, high=80), 0.10),
        (score_linear(volatilidade_30d, low=10, high=80, invert=True), 0.14),
        (score_linear(volatilidade_90d, low=10, high=80, invert=True), 0.10),
        (score_linear(retorno_vs_ibov, low=-25, high=25), 0.10),
        (score_linear(volume_anomaly, low=-2, high=2), 0.04),
    ])


def score_etf_features(*, taxa_adm_rank=None, tracking_score=None, momentum_30d=None, momentum_90d=None, volatilidade_30d=None, retorno_vs_benchmark=None) -> Decimal:
    """ETFs: custos baixos, tracking consistente, momentum moderado e volatilidade controlada."""
    return weighted_score([
        (score_linear(taxa_adm_rank, low=0, high=100), 0.20),
        (score_linear(tracking_score, low=0, high=100), 0.22),
        (score_linear(momentum_30d, low=-15, high=15), 0.12),
        (score_linear(momentum_90d, low=-25, high=25), 0.16),
        (score_linear(volatilidade_30d, low=5, high=60, invert=True), 0.18),
        (score_linear(retorno_vs_benchmark, low=-10, high=10), 0.12),
    ])


def score_bdr_features(*, cambio_trend_30d=None, momentum_30d=None, momentum_90d=None, volatilidade_30d=None, retorno_vs_spy=None, liquidez_score=None) -> Decimal:
    """BDRs: penaliza risco cambial/volatilidade e premia liquidez e retorno relativo."""
    return weighted_score([
        (score_linear(abs(float(cambio_trend_30d)) if cambio_trend_30d is not None else None, low=0, high=10, invert=True), 0.15),
        (score_linear(momentum_30d, low=-20, high=20), 0.14),
        (score_linear(momentum_90d, low=-30, high=30), 0.16),
        (score_linear(volatilidade_30d, low=10, high=90, invert=True), 0.20),
        (score_linear(retorno_vs_spy, low=-25, high=25), 0.20),
        (score_linear(liquidez_score, low=0, high=100), 0.15),
    ])


def score_cripto_features(*, volatilidade_7d=None, volatilidade_30d=None, correlacao_btc_30d=None, momentum_7d=None, momentum_30d=None, momentum_90d=None, volume_anomaly=None, fear_greed_score=None) -> Decimal:
    """Cripto: maior penalização para volatilidade extrema e euforia, premia momentum controlado e volume saudável."""
    fear_component = None
    if fear_greed_score is not None:
        fear = float(fear_greed_score)
        fear_component = 100 - abs(fear - 50) * 2
    return weighted_score([
        (score_linear(volatilidade_7d, low=20, high=180, invert=True), 0.16),
        (score_linear(volatilidade_30d, low=20, high=180, invert=True), 0.18),
        (score_linear(abs(float(correlacao_btc_30d)) if correlacao_btc_30d is not None else None, low=0, high=1, invert=True), 0.08),
        (score_linear(momentum_7d, low=-25, high=25), 0.10),
        (score_linear(momentum_30d, low=-40, high=40), 0.16),
        (score_linear(momentum_90d, low=-60, high=80), 0.12),
        (score_linear(volume_anomaly, low=-2, high=2), 0.10),
        (fear_component, 0.10),
    ])
