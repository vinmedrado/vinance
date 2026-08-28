from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.models import MarketCandle
from backend.trading.prediction_engine.models import LoadedArtifacts, ManifestEntry

from backend.trading.backtesting_v2.config import BacktestingConfig
from backend.trading.backtesting_v2.models import HistoricalCandle


FEATURE_COLUMNS = ("f1", "f2")


class IdentityPreprocessing:
    feature_columns = FEATURE_COLUMNS

    def __init__(self):
        self.transform_calls = 0
        self.seen_frames = []

    def transform(self, frame):
        self.transform_calls += 1
        self.seen_frames.append(frame.copy())
        return frame


class StaticModel:
    classes_ = np.array([-1, 0, 1])

    def __init__(self, probabilities=(0.10, 0.20, 0.70)):
        self.probabilities = probabilities
        self.seen_frames = []
        self.predict_calls = 0
        self.predict_proba_calls = 0

    def predict(self, transformed):
        self.predict_calls += 1
        self.seen_frames.append(transformed.copy())
        predicted = int(self.classes_[int(np.argmax(self.probabilities))])
        return np.full(len(transformed), predicted, dtype=int)

    def predict_proba(self, transformed):
        self.predict_proba_calls += 1
        return np.tile(np.asarray(self.probabilities, dtype=float), (len(transformed), 1))


def artifacts(model=None) -> LoadedArtifacts:
    entry = ManifestEntry(
        symbol="BTCUSDT",
        interval="5m",
        target_name="v2_long_tp_100bps_sl_50bps_h_24",
        model_name="fake_model",
        feature_version="v2",
        ml_engine_version="v2",
        is_best=True,
        artifact_dir=Path("artifact"),
        generated_at="2026-01-01T00:00:00+00:00",
        metadata={},
    )
    return LoadedArtifacts(
        entry=entry,
        model=model or StaticModel(),
        preprocessing=IdentityPreprocessing(),
        feature_columns=FEATURE_COLUMNS,
        metadata={
            "symbol": "BTCUSDT",
            "interval": "5m",
            "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
            "model_name": "fake_model",
            "feature_version": "v2",
            "ml_engine_version": "v2",
            "generated_at": "2026-01-01T00:00:00+00:00",
        },
    )


def config(tmp_path, **kwargs) -> BacktestingConfig:
    paper = kwargs.pop("paper_config", PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0, cooldown_candles=0))
    return BacktestingConfig(output_root=tmp_path, paper_config=paper, timestamp="2026-01-01T00:00:00+00:00", **kwargs)


def history(
    count: int = 8,
    *,
    close: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    start: datetime | None = None,
) -> list[HistoricalCandle]:
    base = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        price = close + index * 0.1
        rows.append(
            HistoricalCandle(
                candle=MarketCandle(
                    candle_id=index + 1,
                    symbol="BTCUSDT",
                    interval="5m",
                    open_time=base + timedelta(minutes=5 * index),
                    open=price,
                    high=high if high is not None else price,
                    low=low if low is not None else price,
                    close=price,
                ),
                features={"f1": float(index), "f2": float(index + 1)},
            )
        )
    return rows


def scenario_history(*, exit_kind: str) -> list[HistoricalCandle]:
    rows = history(2, close=100.0)
    if exit_kind == "tp":
        rows[1] = HistoricalCandle(MarketCandle(2, "BTCUSDT", "5m", rows[1].candle.open_time, 100, 101.5, 100, 101), rows[1].features)
    elif exit_kind == "sl":
        rows[1] = HistoricalCandle(MarketCandle(2, "BTCUSDT", "5m", rows[1].candle.open_time, 100, 100, 99.4, 99.5), rows[1].features)
    elif exit_kind == "both":
        rows[1] = HistoricalCandle(MarketCandle(2, "BTCUSDT", "5m", rows[1].candle.open_time, 100, 101.5, 99.4, 100), rows[1].features)
    elif exit_kind == "horizon":
        rows = history(30, close=100.0, high=100.2, low=99.9)
    return rows
