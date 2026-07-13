from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from pandas.testing import assert_frame_equal

from backend.trading.target_engine.builder import TargetBuilder
from backend.trading.target_engine.config import DEFAULT_CONFIG, TargetEngineConfig
from backend.trading.target_engine.pipeline import TargetEnginePipeline


def deterministic_candles(rows: int = 220) -> pd.DataFrame:
    close = pd.Series([100 + index * 0.08 + (index % 9) * 0.04 for index in range(rows)], dtype=float)
    return pd.DataFrame(
        {
            "id": range(1, rows + 1),
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "interval": "5m",
            "open_time": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "high": close + 0.7 + (pd.Series(range(rows)) % 4) * 0.03,
            "low": close - 0.7 - (pd.Series(range(rows)) % 5) * 0.03,
            "close": close,
        }
    )


class InMemoryTargetRepository:
    def __init__(self, candles: pd.DataFrame, config: TargetEngineConfig = DEFAULT_CONFIG) -> None:
        self.candles = candles.copy()
        self.config = config
        self.persisted: dict[tuple[int, str], dict[str, Any]] = {}
        self.persist_calls: list[int] = []

    def ensure_schema(self) -> None:
        return None

    def get_last_target_time(self, symbol: str, interval: str, exchange: str, specs) -> datetime | None:
        if not self.persisted:
            return None
        ids = {candle_id for candle_id, _target_name in self.persisted}
        persisted = self.candles[self.candles["id"].isin(ids)].sort_values("open_time")
        latest = persisted["open_time"].iloc[-1]
        return latest.to_pydatetime() if hasattr(latest, "to_pydatetime") else latest

    def load_full_history_for_build(self, symbol: str, interval: str, exchange: str, limit: int | None = None):
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

    def persist_targets(self, frame: pd.DataFrame, specs, *, only_after: datetime | None = None) -> int:
        usable = frame.copy()
        if only_after is not None:
            usable = usable[usable["open_time"] > only_after]
        saved = 0
        for row in usable.itertuples(index=False):
            for spec in specs:
                class_col = f"{spec.name}_class"
                return_col = f"{spec.name}_exit_return"
                target_class = getattr(row, class_col)
                target_value = getattr(row, return_col)
                if pd.isna(target_class) or pd.isna(target_value):
                    continue
                self.persisted[(int(row.id), spec.name)] = {
                    "target_class": int(target_class),
                    "target_value": float(target_value),
                }
                saved += 1
        self.persist_calls.append(saved)
        return saved

    def persisted_frame(self, ids: list[int], target_names: tuple[str, ...]) -> pd.DataFrame:
        rows = []
        index = []
        for candle_id in ids:
            for target_name in target_names:
                rows.append(self.persisted[(candle_id, target_name)])
                index.append((candle_id, target_name))
        return pd.DataFrame(rows, index=pd.MultiIndex.from_tuples(index, names=["id", "target_name"]))


def test_incremental_targets_match_full_rebuild_for_new_candles() -> None:
    all_candles = deterministic_candles()
    initial = all_candles.iloc[:150].copy()
    new_ids = all_candles.iloc[150:]["id"].tolist()

    builder = TargetBuilder()
    full = builder.build(all_candles).frame.set_index("id")
    target_names = tuple(spec.name for spec in DEFAULT_CONFIG.specs)

    repository = InMemoryTargetRepository(initial)
    pipeline = TargetEnginePipeline(engine=None, builder=builder, repository=repository)  # type: ignore[arg-type]
    first = pipeline.run_symbol("BTCUSDT", "5m")
    assert first.targets_persisted > 0

    repository.candles = all_candles.copy()
    second = pipeline.run_symbol("BTCUSDT", "5m")
    assert second.targets_persisted > 0

    expected_rows = []
    expected_index = []
    for candle_id in new_ids:
        for spec in DEFAULT_CONFIG.specs:
            class_value = full.loc[candle_id, f"{spec.name}_class"]
            target_value = full.loc[candle_id, f"{spec.name}_exit_return"]
            if pd.isna(class_value) or pd.isna(target_value):
                continue
            expected_rows.append({"target_class": int(class_value), "target_value": float(target_value)})
            expected_index.append((candle_id, spec.name))
    expected = pd.DataFrame(expected_rows, index=pd.MultiIndex.from_tuples(expected_index, names=["id", "target_name"]))
    actual = repository.persisted_frame([idx[0] for idx in expected_index[:: len(target_names)]], target_names)
    actual = actual.loc[expected.index]

    assert_frame_equal(actual, expected, check_exact=False, rtol=1e-10, atol=1e-10)

    third = pipeline.run_symbol("BTCUSDT", "5m")
    assert third.targets_persisted == 0


def test_incremental_targets_report_history_truncated() -> None:
    config = TargetEngineConfig(default_limit=80)
    repository = InMemoryTargetRepository(deterministic_candles(rows=120), config=config)
    pipeline = TargetEnginePipeline(
        engine=None,
        config=config,
        builder=TargetBuilder(config),
        repository=repository,  # type: ignore[arg-type]
    )
    result = pipeline.run_symbol("BTCUSDT", "5m")
    assert result.candles_loaded == 80
    assert result.metadata["history_truncated"] == 1
