import pandas as pd

from ..targets.builder import build_direction_target


def test_target_builder() -> None:
    frame = pd.DataFrame({"close": [100, 101, 102, 103]})
    result = build_direction_target(frame, horizon_candles=1, threshold_pct=0.005)
    assert "target_class" in result.columns
