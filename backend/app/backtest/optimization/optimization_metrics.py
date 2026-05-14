from typing import Dict, Iterable, List


def _norm(value: float, good: float, bad: float, inverse: bool = False) -> float:
    if value is None:
        return 0.0
    try:
        v = float(value)
    except Exception:
        return 0.0
    if inverse:
        score = (bad - v) / (bad - good) if bad != good else 0.0
    else:
        score = (v - bad) / (good - bad) if good != bad else 0.0
    return max(0.0, min(100.0, score * 100.0))


def robustness_score(metrics: Dict, window_returns: Iterable[float] = (), total_assets: int = 0) -> float:
    """Score 0-100 com penalizações explícitas contra overfitting."""
    annual = float(metrics.get('annual_return') or 0)
    drawdown = abs(float(metrics.get('max_drawdown') or 0))
    sharpe = float(metrics.get('sharpe_ratio') or 0)
    trades = int(metrics.get('total_trades') or 0)
    returns = [float(x) for x in window_returns if x is not None]

    score_return = _norm(annual, good=0.25, bad=-0.10)
    score_dd = _norm(drawdown, good=0.05, bad=0.50, inverse=True)
    score_sharpe = _norm(sharpe, good=1.5, bad=-0.5)
    score_trades = _norm(trades, good=40, bad=3)
    if returns:
        positive_ratio = sum(1 for r in returns if r > 0) / len(returns)
        dispersion = max(returns) - min(returns) if len(returns) > 1 else 0
        score_stability = max(0.0, min(100.0, positive_ratio * 80 + _norm(dispersion, good=0.05, bad=0.80, inverse=True) * 0.20))
    else:
        score_stability = 50.0

    concentration_penalty = 0.0
    if total_assets and total_assets < 3:
        concentration_penalty = 15.0
    few_trades_penalty = 20.0 if trades < 5 else 0.0

    score = (
        score_return * 0.25 +
        score_dd * 0.25 +
        score_sharpe * 0.25 +
        score_stability * 0.15 +
        score_trades * 0.10
    ) - concentration_penalty - few_trades_penalty
    return round(max(0.0, min(100.0, score)), 2)
