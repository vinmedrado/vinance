from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import REQUIRED_CANDLE_COLUMNS


def as_numeric_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_CANDLE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing candle columns: {sorted(missing)}")

    result = frame.sort_values("open_time").copy()
    for column in ("open", "high", "low", "close", "volume", "quote_volume"):
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def safe_divide(numerator: pd.Series, denominator: pd.Series | float) -> pd.Series:
    denominator_series = denominator if isinstance(denominator, pd.Series) else pd.Series(denominator, index=numerator.index)
    return numerator / denominator_series.replace(0, np.nan)


def clean_feature_frame(frame: pd.DataFrame, feature_columns: tuple[str, ...]) -> pd.DataFrame:
    result = frame.copy()
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    for column in feature_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result
