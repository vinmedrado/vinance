from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import safe_divide


def add_rsi(frame: pd.DataFrame, periods: tuple[int, ...] = (14,)) -> pd.DataFrame:
    close = frame["close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    for period in periods:
        avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        rs = safe_divide(avg_gain, avg_loss)
        frame[f"rsi_{period}"] = 100 - (100 / (1 + rs))
    return frame


def add_macd(frame: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    close = frame["close"]
    fast_ema = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
    slow_ema = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    macd = fast_ema - slow_ema
    signal_line = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    frame[f"macd_{fast}_{slow}"] = macd
    frame[f"macd_signal_{signal}"] = signal_line
    frame[f"macd_hist_{fast}_{slow}_{signal}"] = macd - signal_line
    return frame


def add_roc(frame: pd.DataFrame, periods: tuple[int, ...] = (10, 20)) -> pd.DataFrame:
    close = frame["close"]
    for period in periods:
        frame[f"roc_{period}"] = close.pct_change(period)
    return frame


def add_cci(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    mean = typical.rolling(period, min_periods=period).mean()
    mean_deviation = typical.rolling(period, min_periods=period).apply(
        lambda values: float(np.mean(np.abs(values - np.mean(values)))),
        raw=True,
    )
    frame[f"cci_{period}"] = safe_divide(typical - mean, 0.015 * mean_deviation)
    return frame


def add_williams_r(frame: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    highest = frame["high"].rolling(period, min_periods=period).max()
    lowest = frame["low"].rolling(period, min_periods=period).min()
    frame[f"williams_r_{period}"] = -100 * safe_divide(highest - frame["close"], highest - lowest)
    return frame


def add_stochastic(frame: pd.DataFrame, period: int = 14, smooth: int = 3) -> pd.DataFrame:
    highest = frame["high"].rolling(period, min_periods=period).max()
    lowest = frame["low"].rolling(period, min_periods=period).min()
    k = 100 * safe_divide(frame["close"] - lowest, highest - lowest)
    frame[f"stoch_k_{period}"] = k
    frame[f"stoch_d_{period}_{smooth}"] = k.rolling(smooth, min_periods=smooth).mean()
    return frame
