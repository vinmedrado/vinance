from __future__ import annotations

import math
from .metrics_base import avg


def _log_returns(rows: list[dict]) -> list[float]:
    vals = []
    closes = [float(r["close"]) for r in rows if r.get("close") is not None and float(r["close"]) > 0]
    for prev, curr in zip(closes, closes[1:]):
        vals.append(math.log(curr / prev))
    return vals


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    m = sum(values) / len(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def _max_drawdown(closes: list[float]) -> float | None:
    if not closes:
        return None
    peak = closes[0]
    max_dd = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak > 0:
            max_dd = min(max_dd, (close / peak) - 1)
    return max_dd


def calculate_risk_metrics(rows: list[dict]) -> dict:
    closes = [float(r["close"]) for r in rows if r.get("close") is not None and float(r["close"]) > 0]
    lr = _log_returns(rows)
    lr30 = lr[-30:]
    lr90 = lr[-90:]
    vol30 = (_stdev(lr30) or 0) * math.sqrt(252) if len(lr30) >= 2 else None
    vol90 = (_stdev(lr90) or 0) * math.sqrt(252) if len(lr90) >= 2 else None
    negative = [v for v in lr90 if v < 0]
    downside = (_stdev(negative) or 0) * math.sqrt(252) if len(negative) >= 2 else None
    mean90 = avg(lr90)
    sharpe = (mean90 * 252) / vol90 if mean90 is not None and vol90 and vol90 > 0 else None
    return {
        "volatilidade_30d": vol30,
        "volatilidade_90d": vol90,
        "drawdown_maximo": _max_drawdown(closes),
        "sharpe_aproximado": sharpe,
        "downside_risk": downside,
    }
