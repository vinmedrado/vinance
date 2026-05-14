from __future__ import annotations

from .metrics_base import clamp

WEIGHTS = {
    "fii": {"retorno": 0.20, "risco": 0.20, "liquidez": 0.20, "dividendos": 0.40, "tendencia": 0.00},
    "crypto": {"retorno": 0.35, "risco": 0.25, "liquidez": 0.10, "dividendos": 0.00, "tendencia": 0.30},
    "index": {"retorno": 0.30, "risco": 0.25, "liquidez": 0.05, "dividendos": 0.00, "tendencia": 0.40},
    "currency": {"retorno": 0.30, "risco": 0.30, "liquidez": 0.05, "dividendos": 0.00, "tendencia": 0.35},
    "commodity": {"retorno": 0.30, "risco": 0.30, "liquidez": 0.05, "dividendos": 0.00, "tendencia": 0.35},
    "etf": {"retorno": 0.30, "risco": 0.25, "liquidez": 0.20, "dividendos": 0.05, "tendencia": 0.20},
    "bdr": {"retorno": 0.30, "risco": 0.30, "liquidez": 0.20, "dividendos": 0.00, "tendencia": 0.20},
    "equity": {"retorno": 0.30, "risco": 0.25, "liquidez": 0.20, "dividendos": 0.10, "tendencia": 0.15},
    "unknown": {"retorno": 0.30, "risco": 0.30, "liquidez": 0.20, "dividendos": 0.00, "tendencia": 0.20},
}


def _score_return(metrics: dict) -> float | None:
    r90 = metrics.get("retorno_90d")
    r365 = metrics.get("retorno_365d")
    base = r365 if r365 is not None else r90
    if base is None:
        return None
    return clamp(50 + (float(base) * 100))


def _score_risk(metrics: dict) -> float | None:
    vol = metrics.get("volatilidade_90d") or metrics.get("volatilidade_30d")
    dd = abs(metrics.get("drawdown_maximo") or 0)
    if vol is None:
        return None
    raw = 100 - (float(vol) * 100) - (dd * 50)
    return clamp(raw)


def _score_liquidity(metrics: dict) -> float | None:
    return clamp(metrics.get("liquidez_score"))


def _score_dividends(metrics: dict) -> float | None:
    dy = metrics.get("dividend_yield_12m")
    freq = metrics.get("frequencia_dividendos") or 0
    if dy is None:
        return 0
    return clamp(float(dy) * 800 + min(freq, 12) * 2)


def _score_trend(metrics: dict) -> float | None:
    signals = []
    for key in ["distancia_mm20", "distancia_mm50", "distancia_mm200"]:
        v = metrics.get(key)
        if v is not None:
            signals.append(float(v))
    if not signals:
        return None
    avg = sum(signals) / len(signals)
    return clamp(50 + avg * 200)


def calculate_score(asset_class: str | None, metrics: dict) -> dict:
    asset_class = asset_class or "unknown"
    weights = WEIGHTS.get(asset_class, WEIGHTS["unknown"])
    components = {
        "score_retorno": _score_return(metrics),
        "score_risco": _score_risk(metrics),
        "score_liquidez": _score_liquidity(metrics),
        "score_dividendos": _score_dividends(metrics),
        "score_tendencia": _score_trend(metrics),
    }
    weighted = []
    weight_map = {
        "score_retorno": weights["retorno"],
        "score_risco": weights["risco"],
        "score_liquidez": weights["liquidez"],
        "score_dividendos": weights["dividendos"],
        "score_tendencia": weights["tendencia"],
    }
    for key, value in components.items():
        w = weight_map[key]
        if w > 0 and value is not None:
            weighted.append((value, w))
    if not weighted:
        total = None
        explanation = "Score não calculado por dados insuficientes."
    else:
        total_weight = sum(w for _, w in weighted)
        total = sum(v * w for v, w in weighted) / total_weight
        explanation = (
            f"Score explicável por classe {asset_class}: retorno={components['score_retorno']}, "
            f"risco={components['score_risco']}, liquidez={components['score_liquidez']}, "
            f"dividendos={components['score_dividendos']}, tendência={components['score_tendencia']}. "
            "Não é recomendação de compra ou venda."
        )
    return {**components, "score_total": clamp(total) if total is not None else None, "explanation": explanation}
