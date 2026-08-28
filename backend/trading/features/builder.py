from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_VERSION = "v1"


def build_features(candles: pd.DataFrame) -> pd.DataFrame:
    frame = candles.sort_values("open_time").copy()
    close = pd.to_numeric(frame["close"], errors="coerce")
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    volume = pd.to_numeric(frame["volume"], errors="coerce")

    frame["return_1"] = close.pct_change()
    frame["return_3"] = close.pct_change(3)
    frame["return_12"] = close.pct_change(12)
    frame["ema_9"] = close.ewm(span=9, adjust=False).mean()
    frame["ema_21"] = close.ewm(span=21, adjust=False).mean()
    frame["volatility_12"] = frame["return_1"].rolling(12).std()
    frame["volume_zscore_24"] = (volume - volume.rolling(24).mean()) / volume.rolling(24).std()
    frame["range_pct"] = (high - low) / close.replace(0, np.nan)

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi_14"] = 100 - (100 / (1 + rs))

    return frame
