from __future__ import annotations

import numpy as np
import pandas as pd

from .config import DEFAULT_CONFIG, TargetEngineConfig, TargetSpec
from .models import TargetBuildResult


REQUIRED_COLUMNS = ("id", "exchange", "symbol", "interval", "open_time", "high", "low", "close")


class TargetBuilder:
    def __init__(self, config: TargetEngineConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def build(self, candles: pd.DataFrame) -> TargetBuildResult:
        frame = _prepare_candles(candles)
        target_columns: list[str] = []
        for spec in self.config.specs:
            frame = self._apply_spec(frame, spec)
            target_columns.extend(_columns_for_spec(spec))
        return TargetBuildResult(
            frame=frame,
            specs=self.config.specs,
            target_version=self.config.target_version,
            target_columns=tuple(target_columns),
        )

    def _apply_spec(self, frame: pd.DataFrame, spec: TargetSpec) -> pd.DataFrame:
        classes: list[int | float] = []
        event_times: list[int | float] = []
        exit_returns: list[float] = []

        highs = frame["high"].to_numpy(dtype=float)
        lows = frame["low"].to_numpy(dtype=float)
        closes = frame["close"].to_numpy(dtype=float)
        total = len(frame)

        for index in range(total):
            entry = closes[index]
            if not np.isfinite(entry) or entry <= 0:
                classes.append(np.nan)
                event_times.append(np.nan)
                exit_returns.append(np.nan)
                continue

            end = min(index + spec.horizon_candles, total - 1)
            if end <= index:
                classes.append(np.nan)
                event_times.append(np.nan)
                exit_returns.append(np.nan)
                continue

            target_class = 0
            event_time = spec.horizon_candles
            exit_price = closes[end]

            for future_index in range(index + 1, end + 1):
                high = highs[future_index]
                low = lows[future_index]
                if spec.side == "long":
                    take_profit_price = entry * (1 + spec.take_profit_pct)
                    stop_loss_price = entry * (1 - spec.stop_loss_pct)
                    hit_tp = high >= take_profit_price
                    hit_sl = low <= stop_loss_price
                    if hit_tp or hit_sl:
                        target_class = 1 if hit_tp else -1
                        exit_price = take_profit_price if hit_tp else stop_loss_price
                        event_time = future_index - index
                        break
                else:
                    take_profit_price = entry * (1 - spec.take_profit_pct)
                    stop_loss_price = entry * (1 + spec.stop_loss_pct)
                    hit_tp = low <= take_profit_price
                    hit_sl = high >= stop_loss_price
                    if hit_tp or hit_sl:
                        target_class = 1 if hit_tp else -1
                        exit_price = take_profit_price if hit_tp else stop_loss_price
                        event_time = future_index - index
                        break

            if spec.side == "long":
                exit_return = exit_price / entry - 1
            else:
                exit_return = entry / exit_price - 1

            classes.append(target_class)
            event_times.append(event_time)
            exit_returns.append(float(exit_return))

        class_col, time_col, return_col = _columns_for_spec(spec)
        frame[class_col] = classes
        frame[time_col] = event_times
        frame[return_col] = exit_returns
        return frame


def _prepare_candles(candles: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_COLUMNS).difference(candles.columns)
    if missing:
        raise ValueError(f"Missing candle columns: {sorted(missing)}")
    frame = candles.sort_values("open_time").copy()
    for column in ("high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.reset_index(drop=True)


def _columns_for_spec(spec: TargetSpec) -> tuple[str, str, str]:
    prefix = spec.name
    return f"{prefix}_class", f"{prefix}_time_to_event", f"{prefix}_exit_return"


def build_targets_v2(candles: pd.DataFrame) -> pd.DataFrame:
    return TargetBuilder().build(candles).frame
