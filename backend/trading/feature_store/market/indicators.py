from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import safe_divide


def add_market_context(frame: pd.DataFrame) -> pd.DataFrame:
    frame["return_1"] = frame["close"].pct_change()
    frame["return_3"] = frame["close"].pct_change(3)
    frame["return_12"] = frame["close"].pct_change(12)

    ratio = frame["close"] / frame["close"].shift(1)
    frame["log_return_1"] = np.log(ratio.where(ratio > 0))

    frame["range_pct"] = safe_divide(frame["high"] - frame["low"], frame["close"])
    frame["close_position_in_range"] = safe_divide(frame["close"] - frame["low"], frame["high"] - frame["low"])
    frame["volume_zscore_24"] = safe_divide(
        frame["volume"] - frame["volume"].rolling(24, min_periods=24).mean(),
        frame["volume"].rolling(24, min_periods=24).std(ddof=0),
    )
    return frame
