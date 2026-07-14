from __future__ import annotations

from backend.trading.ml_engine.config import PROHIBITED_FEATURE_COLUMNS
from backend.trading.ml_engine.dataset import temporal_split, walk_forward_splits
from backend.trading.ml_engine.tests.helpers import synthetic_dataset


def test_dataset_is_temporally_ordered_and_joined() -> None:
    dataset = synthetic_dataset(120)
    assert dataset.sample_count == 120
    assert dataset.frame["open_time"].is_monotonic_increasing
    assert {"feature_a", "feature_b", "feature_c"}.issubset(dataset.feature_columns)


def test_dataset_excludes_prohibited_and_all_null_columns() -> None:
    dataset = synthetic_dataset(120)
    assert not PROHIBITED_FEATURE_COLUMNS.intersection(dataset.feature_columns)
    assert "all_null" not in dataset.feature_columns
    assert "target_class" not in dataset.feature_columns


def test_temporal_split_is_chronological() -> None:
    dataset = synthetic_dataset(200)
    split = temporal_split(dataset)
    assert len(split.train) == 140
    assert len(split.validation) == 30
    assert len(split.test) == 30
    assert split.train["open_time"].max() < split.validation["open_time"].min()
    assert split.validation["open_time"].max() < split.test["open_time"].min()


def test_walk_forward_has_no_overlap_between_train_and_validation() -> None:
    dataset = synthetic_dataset(240)
    windows = list(walk_forward_splits(dataset, windows=3))
    assert windows
    for split in windows:
        assert split.train["open_time"].max() < split.validation["open_time"].min()
        assert split.validation["open_time"].max() < split.test["open_time"].min()
