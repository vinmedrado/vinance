import math

def pct_return(prices: list[float], periods: int):
    clean = [p for p in prices if p is not None and p > 0]
    if len(clean) <= periods:
        return None
    return (clean[-1] / clean[-periods-1]) - 1

def volatility(prices: list[float]):
    clean = [p for p in prices if p is not None and p > 0]
    if len(clean) < 3:
        return None
    rets = [(clean[i] / clean[i-1]) - 1 for i in range(1, len(clean))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
    return math.sqrt(var) * math.sqrt(252)

def max_drawdown(prices: list[float]):
    peak = None; max_dd = 0.0
    for p in prices:
        if p is None or p <= 0: continue
        peak = p if peak is None else max(peak, p)
        max_dd = min(max_dd, (p / peak) - 1)
    return max_dd

def normalize(value, low, high, inverse=False):
    if value is None or high == low:
        return 0.5
    x = max(0.0, min(1.0, (value - low) / (high - low)))
    return 1 - x if inverse else x
