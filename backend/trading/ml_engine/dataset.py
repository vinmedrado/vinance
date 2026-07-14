from __future__ import annotations

import json
from collections.abc import Iterator

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import DEFAULT_CONFIG, MLEngineConfig, PROHIBITED_FEATURE_COLUMNS, SplitConfig
from .models import TemporalSplit, TradingDataset


class DatasetRepository:
    def __init__(self, engine: Engine, config: MLEngineConfig = DEFAULT_CONFIG) -> None:
        self.engine = engine
        self.config = config

    def load_dataset(
        self,
        *,
        symbol: str,
        interval: str,
        target_name: str,
        limit: int | None = None,
    ) -> TradingDataset:
        query = text(
            """
            SELECT
                c.id AS candle_id,
                c.open_time,
                f.features,
                t.target_name,
                t.target_value,
                t.target_class
            FROM crypto_features f
            JOIN crypto_candles c ON c.id = f.candle_id
            JOIN crypto_targets t ON t.candle_id = c.id
            WHERE f.feature_version = :feature_version
              AND c.symbol = :symbol
              AND c.interval = :interval
              AND t.target_name = :target_name
              AND t.target_name LIKE :target_prefix
            ORDER BY c.open_time ASC
            """
        )
        frame = pd.read_sql(
            query,
            self.engine,
            params={
                "feature_version": self.config.feature_version,
                "symbol": symbol,
                "interval": interval,
                "target_name": target_name,
                "target_prefix": f"{self.config.target_prefix}%",
            },
        )
        if limit is not None:
            frame = frame.tail(limit).reset_index(drop=True)
        return build_dataset_from_joined_frame(frame, symbol=symbol, interval=interval, target_name=target_name)


def build_dataset_from_joined_frame(
    frame: pd.DataFrame,
    *,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    target_name: str = "v2_test",
) -> TradingDataset:
    if frame.empty:
        return TradingDataset(frame=frame, feature_columns=(), symbol=symbol, interval=interval, target_name=target_name)

    expanded = _expand_features(frame["features"])
    expanded = expanded.drop(columns=[column for column in expanded.columns if column in PROHIBITED_FEATURE_COLUMNS], errors="ignore")
    result = pd.concat([frame.drop(columns=["features"]).reset_index(drop=True), expanded.reset_index(drop=True)], axis=1)
    result = result.sort_values("open_time").reset_index(drop=True)
    result["target_class"] = pd.to_numeric(result["target_class"], errors="coerce")
    result["target_value"] = pd.to_numeric(result["target_value"], errors="coerce")
    result = result.dropna(subset=["target_class", "target_value"])
    result["target_class"] = result["target_class"].astype(int)

    candidate_features = [
        column
        for column in expanded.columns
        if column not in PROHIBITED_FEATURE_COLUMNS and not result[column].isna().all()
    ]
    for column in candidate_features:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    return TradingDataset(
        frame=result,
        feature_columns=tuple(candidate_features),
        symbol=symbol,
        interval=interval,
        target_name=target_name,
    )


def temporal_split(dataset: TradingDataset, split: SplitConfig = SplitConfig()) -> TemporalSplit:
    frame = dataset.frame.sort_values("open_time").reset_index(drop=True)
    train_end = int(len(frame) * split.train_pct)
    validation_end = train_end + int(len(frame) * split.validation_pct)
    return TemporalSplit(
        train=frame.iloc[:train_end].copy(),
        validation=frame.iloc[train_end:validation_end].copy(),
        test=frame.iloc[validation_end:].copy(),
    )


def walk_forward_splits(
    dataset: TradingDataset,
    *,
    windows: int = 3,
    min_train_pct: float = 0.50,
    validation_pct: float = 0.15,
) -> Iterator[TemporalSplit]:
    frame = dataset.frame.sort_values("open_time").reset_index(drop=True)
    total = len(frame)
    min_train = int(total * min_train_pct)
    validation_size = max(int(total * validation_pct), 1)
    for index in range(windows):
        train_end = min_train + index * validation_size
        validation_end = train_end + validation_size
        test_end = min(validation_end + validation_size, total)
        if train_end <= 0 or validation_end >= total or test_end <= validation_end:
            break
        yield TemporalSplit(
            train=frame.iloc[:train_end].copy(),
            validation=frame.iloc[train_end:validation_end].copy(),
            test=frame.iloc[validation_end:test_end].copy(),
        )


def _expand_features(series: pd.Series) -> pd.DataFrame:
    rows = []
    for value in series:
        if isinstance(value, str):
            rows.append(json.loads(value))
        elif isinstance(value, dict):
            rows.append(value)
        else:
            rows.append(dict(value or {}))
    return pd.DataFrame(rows)
