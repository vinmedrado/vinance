from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from pandas.testing import assert_frame_equal

from backend.trading.feature_store.builder import FeatureBuilder
from backend.trading.feature_store.config import DEFAULT_CONFIG, FeatureStoreConfig
from backend.trading.feature_store.pipeline import FeatureStorePipeline


def deterministic_candles(rows: int = 360) -> pd.DataFrame:
    close = pd.Series(
        [100 + index * 0.11 + (index % 11) * 0.07 - (index % 5) * 0.03 for index in range(rows)],
        dtype=float,
    )
    return pd.DataFrame(
        {
            "id": range(1, rows + 1),
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "interval": "5m",
            "open_time": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "close_time": pd.date_range("2026-01-01 00:04:59", periods=rows, freq="5min", tz="UTC"),
            "open": close - 0.13,
            "high": close + 0.91 + (pd.Series(range(rows)) % 3) * 0.02,
            "low": close - 0.84 - (pd.Series(range(rows)) % 4) * 0.02,
            "close": close,
            "volume": pd.Series([1000 + (index % 31) * 17 + index * 0.5 for index in range(rows)], dtype=float),
            "quote_volume": pd.Series([100_000 + index * 10 for index in range(rows)], dtype=float),
            "trades": pd.Series([100 + index % 10 for index in range(rows)], dtype=int),
        }
    )


class InMemoryFeatureRepository:
    def __init__(self, candles: pd.DataFrame, config: FeatureStoreConfig = DEFAULT_CONFIG) -> None:
        self.candles = candles.copy()
        self.config = config
        self.persisted: dict[int, dict[str, Any]] = {}
        self.persist_calls: list[int] = []

    def ensure_schema(self) -> None:
        return None

    def get_last_feature_time(self, symbol: str, interval: str, exchange: str, feature_version: str) -> datetime | None:
        if not self.persisted:
            return None
        ids = set(self.persisted)
        persisted = self.candles[self.candles["id"].isin(ids)].sort_values("open_time")
        latest = persisted["open_time"].iloc[-1]
        return latest.to_pydatetime() if hasattr(latest, "to_pydatetime") else latest

    def load_full_history_for_build(
        self,
        symbol: str,
        interval: str,
        exchange: str,
        limit: int | None = None,
    ) -> tuple[pd.DataFrame, bool]:
        filtered = self.candles[
            (self.candles["symbol"] == symbol)
            & (self.candles["interval"] == interval)
            & (self.candles["exchange"] == exchange)
        ].sort_values("open_time")
        effective_limit = limit or self.config.default_limit
        truncated = len(filtered) > effective_limit
        if truncated:
            filtered = filtered.tail(effective_limit)
        return filtered.reset_index(drop=True), truncated

    def persist_features(
        self,
        frame: pd.DataFrame,
        feature_columns: tuple[str, ...],
        feature_version: str,
        *,
        only_after: datetime | None = None,
    ) -> int:
        usable = frame.copy()
        if only_after is not None:
            usable = usable[usable["open_time"] > only_after]
        saved = 0
        for row in usable.itertuples(index=False):
            values = {column: getattr(row, column) for column in feature_columns}
            non_null_count = sum(pd.notna(value) for value in values.values())
            if non_null_count < self.config.min_non_null_features:
                continue
            self.persisted[int(row.id)] = values
            saved += 1
        self.persist_calls.append(saved)
        return saved

    def persisted_frame(self, ids: list[int], feature_columns: tuple[str, ...]) -> pd.DataFrame:
        rows = [self.persisted[item] for item in ids]
        frame = pd.DataFrame(rows, index=ids, columns=feature_columns)
        frame.index.name = "id"
        return frame


def test_incremental_pipeline_matches_full_rebuild_for_new_candles() -> None:
    all_candles = deterministic_candles()
    initial_candles = all_candles.iloc[:260].copy()
    new_ids = all_candles.iloc[260:]["id"].tolist()

    builder = FeatureBuilder()
    full_rebuild = builder.build(all_candles).frame.set_index("id")
    feature_columns = builder.feature_columns

    repository = InMemoryFeatureRepository(initial_candles)
    pipeline = FeatureStorePipeline(engine=None, builder=builder, repository=repository)  # type: ignore[arg-type]

    first_result = pipeline.run_symbol("BTCUSDT", "5m")
    assert first_result.rows_persisted > 0

    repository.candles = all_candles.copy()
    second_result = pipeline.run_symbol("BTCUSDT", "5m")
    assert second_result.rows_persisted == len(new_ids)

    incremental_new = repository.persisted_frame(new_ids, feature_columns)
    full_new = full_rebuild.loc[new_ids, list(feature_columns)]
    assert_frame_equal(
        incremental_new,
        full_new,
        check_exact=False,
        rtol=1e-10,
        atol=1e-10,
    )

    third_result = pipeline.run_symbol("BTCUSDT", "5m")
    assert third_result.rows_persisted == 0
    assert repository.persist_calls[-1] == 0


def test_incremental_pipeline_reports_history_truncated() -> None:
    candles = deterministic_candles(rows=120)
    config = FeatureStoreConfig(default_limit=80)
    repository = InMemoryFeatureRepository(candles, config=config)
    pipeline = FeatureStorePipeline(
        engine=None,
        config=config,
        builder=FeatureBuilder(config=config),
        repository=repository,  # type: ignore[arg-type]
    )

    result = pipeline.run_symbol("BTCUSDT", "5m")

    assert result.candles_loaded == 80
    assert result.null_counts["_history_truncated"] == 1
