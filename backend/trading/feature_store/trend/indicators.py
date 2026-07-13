from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import safe_divide


def add_sma(frame: pd.DataFrame, windows: tuple[int, ...] = (9, 21, 50, 200)) -> pd.DataFrame:
    close = frame["close"]
    for window in windows:
        frame[f"sma_{window}"] = close.rolling(window, min_periods=window).mean()
    return frame


def add_ema(frame: pd.DataFrame, spans: tuple[int, ...] = (9, 21, 50, 200)) -> pd.DataFrame:
    close = frame["close"]
    for span in spans:
        frame[f"ema_{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    return frame


def add_wma(frame: pd.DataFrame, windows: tuple[int, ...] = (9, 21, 50)) -> pd.DataFrame:
    close = frame["close"]
    for window in windows:
        weights = np.arange(1, window + 1, dtype=float)
        frame[f"wma_{window}"] = close.rolling(window, min_periods=window).apply(
            lambda values, weights=weights: float(np.dot(values, weights) / weights.sum()),
            raw=True,
        )
    return frame


def _wma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=float)
    return series.rolling(window, min_periods=window).apply(
        lambda values: float(np.dot(values, weights) / weights.sum()),
        raw=True,
    )


def add_hma(frame: pd.DataFrame, windows: tuple[int, ...] = (21, 55)) -> pd.DataFrame:
    close = frame["close"]
    for window in windows:
        half = max(int(window / 2), 1)
        sqrt_window = max(int(np.sqrt(window)), 1)
        raw = 2 * _wma(close, half) - _wma(close, window)
        frame[f"hma_{window}"] = _wma(raw, sqrt_window)
    return frame


def add_kama(frame: pd.DataFrame, window: int = 10, fast: int = 2, slow: int = 30) -> pd.DataFrame:
    close = frame["close"].astype(float)
    change = (close - close.shift(window)).abs()
    volatility = close.diff().abs().rolling(window, min_periods=window).sum()
    efficiency = safe_divide(change, volatility).fillna(0.0)
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    smoothing = (efficiency * (fast_sc - slow_sc) + slow_sc) ** 2

    values = [np.nan] * len(close)
    if len(close) > window:
        values[window] = close.iloc[window]
        for index in range(window + 1, len(close)):
            previous = values[index - 1]
            if pd.isna(previous):
                previous = close.iloc[index - 1]
            values[index] = previous + smoothing.iloc[index] * (close.iloc[index] - previous)
    frame[f"kama_{window}_{fast}_{slow}"] = values
    return frame


def add_supertrend(frame: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    hl2 = (high + low) / 2
    basic_upper = hl2 + multiplier * atr
    basic_lower = hl2 - multiplier * atr

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(np.nan, index=frame.index, dtype=float)
    direction = pd.Series(np.nan, index=frame.index, dtype=float)

    for index in range(len(frame)):
        if index == 0 or pd.isna(atr.iloc[index]):
            continue
        if basic_upper.iloc[index] < final_upper.iloc[index - 1] or close.iloc[index - 1] > final_upper.iloc[index - 1]:
            final_upper.iloc[index] = basic_upper.iloc[index]
        else:
            final_upper.iloc[index] = final_upper.iloc[index - 1]

        if basic_lower.iloc[index] > final_lower.iloc[index - 1] or close.iloc[index - 1] < final_lower.iloc[index - 1]:
            final_lower.iloc[index] = basic_lower.iloc[index]
        else:
            final_lower.iloc[index] = final_lower.iloc[index - 1]

        previous_trend = supertrend.iloc[index - 1]
        if pd.isna(previous_trend):
            supertrend.iloc[index] = final_lower.iloc[index] if close.iloc[index] >= hl2.iloc[index] else final_upper.iloc[index]
        elif previous_trend == final_upper.iloc[index - 1]:
            supertrend.iloc[index] = final_lower.iloc[index] if close.iloc[index] > final_upper.iloc[index] else final_upper.iloc[index]
        else:
            supertrend.iloc[index] = final_upper.iloc[index] if close.iloc[index] < final_lower.iloc[index] else final_lower.iloc[index]
        direction.iloc[index] = 1.0 if close.iloc[index] >= supertrend.iloc[index] else -1.0

    suffix = f"{period}_{str(multiplier).replace('.', '_')}"
    frame[f"supertrend_{suffix}"] = supertrend
    frame[f"supertrend_direction_{suffix}"] = direction
    return frame


def add_ichimoku(frame: pd.DataFrame) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    tenkan_high = high.rolling(9, min_periods=9).max()
    tenkan_low = low.rolling(9, min_periods=9).min()
    kijun_high = high.rolling(26, min_periods=26).max()
    kijun_low = low.rolling(26, min_periods=26).min()
    span_b_high = high.rolling(52, min_periods=52).max()
    span_b_low = low.rolling(52, min_periods=52).min()

    frame["ichimoku_tenkan_9"] = (tenkan_high + tenkan_low) / 2
    frame["ichimoku_kijun_26"] = (kijun_high + kijun_low) / 2
    frame["ichimoku_span_a_current"] = (frame["ichimoku_tenkan_9"] + frame["ichimoku_kijun_26"]) / 2
    frame["ichimoku_span_b_current"] = (span_b_high + span_b_low) / 2
    return frame
