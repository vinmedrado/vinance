from __future__ import annotations

import pandas as pd

from backend.trading.feature_store.repository import FeatureStoreRepository
from backend.trading.history_expansion_v2.pipeline import (
    _FullHistoryFeatureRepository,
    _FullHistoryTargetRepository,
)
from backend.trading.target_engine.repository import TargetRepository


def test_feature_persistence_is_batched_without_changing_rows(monkeypatch) -> None:
    calls = []

    def persist(self, frame, feature_columns, feature_version, *, only_after=None):
        calls.append(len(frame))
        return len(frame)

    monkeypatch.setattr(FeatureStoreRepository, "persist_features", persist)
    repository = _FullHistoryFeatureRepository(None, batch_size=3)
    total = repository.persist_features(pd.DataFrame({"id": range(8)}), ("x",), "v2")
    assert calls == [3, 3, 2]
    assert total == 8


def test_target_persistence_is_batched_without_changing_rows(monkeypatch) -> None:
    calls = []

    def persist(self, frame, specs, *, only_after=None):
        calls.append(len(frame))
        return len(frame) * 4

    monkeypatch.setattr(TargetRepository, "persist_targets", persist)
    repository = _FullHistoryTargetRepository(None, batch_size=3)
    total = repository.persist_targets(pd.DataFrame({"id": range(8)}), ("a", "b", "c", "d"))
    assert calls == [3, 3, 2]
    assert total == 32
