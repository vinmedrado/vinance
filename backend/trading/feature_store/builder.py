from __future__ import annotations

import pandas as pd

from .config import DEFAULT_CONFIG, FeatureStoreConfig
from .models import FeatureBuildResult, FeatureSet
from .registry import get_feature_set
from .utils import as_numeric_ohlcv, clean_feature_frame


class FeatureBuilder:
    def __init__(
        self,
        feature_set: FeatureSet | None = None,
        config: FeatureStoreConfig = DEFAULT_CONFIG,
    ) -> None:
        self.feature_set = feature_set or get_feature_set()
        self.config = config

    @property
    def feature_columns(self) -> tuple[str, ...]:
        return self.feature_set.columns

    def build(self, candles: pd.DataFrame) -> FeatureBuildResult:
        frame = as_numeric_ohlcv(candles)
        if frame.empty:
            return FeatureBuildResult(
                frame=frame,
                feature_columns=self.feature_columns,
                version=self.feature_set.version,
                warmup_candles=self.config.warmup_candles,
            )

        for definition in self.feature_set.definitions:
            before = set(frame.columns)
            frame = definition.function(frame)
            missing = set(definition.columns).difference(frame.columns)
            if missing:
                raise RuntimeError(f"Indicator {definition.name} did not create columns: {sorted(missing)}")
            if before == set(frame.columns):
                raise RuntimeError(f"Indicator {definition.name} did not add any columns.")

        frame = clean_feature_frame(frame, self.feature_columns)
        return FeatureBuildResult(
            frame=frame,
            feature_columns=self.feature_columns,
            version=self.feature_set.version,
            warmup_candles=self.config.warmup_candles,
        )


def build_features_v2(candles: pd.DataFrame) -> pd.DataFrame:
    return FeatureBuilder().build(candles).frame
