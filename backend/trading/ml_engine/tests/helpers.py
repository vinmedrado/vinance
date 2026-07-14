from __future__ import annotations

import math

import pandas as pd

from backend.trading.ml_engine.dataset import build_dataset_from_joined_frame


def joined_frame(rows: int = 240) -> pd.DataFrame:
    records = []
    for index in range(rows):
        signal = math.sin(index / 8)
        target_class = 1 if signal > 0.4 else (-1 if signal < -0.4 else 0)
        records.append(
            {
                "candle_id": index + 1,
                "open_time": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(minutes=5 * index),
                "features": {
                    "feature_a": signal,
                    "feature_b": index / rows,
                    "feature_c": None if index % 17 == 0 else signal * 0.5,
                    "all_null": None,
                    "target_class": 999,
                },
                "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
                "target_value": 0.01 if target_class == 1 else (-0.005 if target_class == -1 else 0.001),
                "target_class": target_class,
            }
        )
    return pd.DataFrame(records)


def synthetic_dataset(rows: int = 240):
    return build_dataset_from_joined_frame(joined_frame(rows))
