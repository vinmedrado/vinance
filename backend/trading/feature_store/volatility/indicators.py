from __future__ import annotations

import pandas as pd

from ..utils import safe_divide


def add_atr(frame: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    frame[f"atr_{period}"] = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    frame[f"atr_pct_{period}"] = safe_divide(frame[f"atr_{period}"], close)
    return frame


def add_bollinger(frame: pd.DataFrame, period: int = 20, deviations: float = 2.0) -> pd.DataFrame:
    close = frame["close"]
    middle = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std(ddof=0)
    upper = middle + deviations * std
    lower = middle - deviations * std
    suffix = f"{period}_{str(deviations).replace('.', '_')}"
    frame[f"bollinger_mid_{suffix}"] = middle
    frame[f"bollinger_upper_{suffix}"] = upper
    frame[f"bollinger_lower_{suffix}"] = lower
    frame[f"bollinger_width_{suffix}"] = safe_divide(upper - lower, middle)
    frame[f"bollinger_percent_b_{suffix}"] = safe_divide(close - lower, upper - lower)
    return frame


def add_donchian(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    upper = frame["high"].rolling(period, min_periods=period).max()
    lower = frame["low"].rolling(period, min_periods=period).min()
    frame[f"donchian_upper_{period}"] = upper
    frame[f"donchian_lower_{period}"] = lower
    frame[f"donchian_mid_{period}"] = (upper + lower) / 2
    frame[f"donchian_width_{period}"] = safe_divide(upper - lower, frame["close"])
    return frame


def add_keltner(frame: pd.DataFrame, period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    middle = close.ewm(span=period, adjust=False, min_periods=period).mean()
    atr = true_range.ewm(alpha=1 / atr_period, adjust=False, min_periods=atr_period).mean()
    suffix = f"{period}_{atr_period}_{str(multiplier).replace('.', '_')}"
    frame[f"keltner_mid_{suffix}"] = middle
    frame[f"keltner_upper_{suffix}"] = middle + multiplier * atr
    frame[f"keltner_lower_{suffix}"] = middle - multiplier * atr
    frame[f"keltner_width_{suffix}"] = safe_divide(2 * multiplier * atr, middle)
    return frame
