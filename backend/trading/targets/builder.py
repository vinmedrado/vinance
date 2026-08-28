from __future__ import annotations

import pandas as pd


def build_direction_target(
    frame: pd.DataFrame,
    horizon_candles: int = 12,
    threshold_pct: float = 0.005,
) -> pd.DataFrame:
    result = frame.copy()
    future_close = result["close"].shift(-horizon_candles)
    future_return = future_close / result["close"] - 1
    result["future_return"] = future_return
    result["target_class"] = 0
    result.loc[future_return >= threshold_pct, "target_class"] = 1
    result.loc[future_return <= -threshold_pct, "target_class"] = -1
    return result
