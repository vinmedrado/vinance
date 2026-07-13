from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import safe_divide


def add_vwap(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    volume = frame["volume"].fillna(0)
    rolling_value = (typical * volume).rolling(period, min_periods=period).sum()
    rolling_volume = volume.rolling(period, min_periods=period).sum()
    frame[f"vwap_{period}"] = safe_divide(rolling_value, rolling_volume)
    frame[f"vwap_distance_{period}"] = safe_divide(frame["close"] - frame[f"vwap_{period}"], frame[f"vwap_{period}"])
    return frame


def add_obv(frame: pd.DataFrame) -> pd.DataFrame:
    direction = np.sign(frame["close"].diff()).fillna(0)
    frame["obv"] = (direction * frame["volume"].fillna(0)).cumsum()
    frame["obv_change_20"] = frame["obv"].diff(20)
    return frame


def add_mfi(frame: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3
    raw_money_flow = typical * frame["volume"].fillna(0)
    direction = typical.diff()
    positive = raw_money_flow.where(direction > 0, 0.0)
    negative = raw_money_flow.where(direction < 0, 0.0).abs()
    positive_sum = positive.rolling(period, min_periods=period).sum()
    negative_sum = negative.rolling(period, min_periods=period).sum()
    money_ratio = safe_divide(positive_sum, negative_sum)
    frame[f"mfi_{period}"] = 100 - (100 / (1 + money_ratio))
    return frame


def add_cmf(frame: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    volume = frame["volume"].fillna(0)
    multiplier = safe_divide((close - low) - (high - close), high - low).fillna(0)
    money_flow_volume = multiplier * volume
    frame[f"cmf_{period}"] = safe_divide(
        money_flow_volume.rolling(period, min_periods=period).sum(),
        volume.rolling(period, min_periods=period).sum(),
    )
    return frame
