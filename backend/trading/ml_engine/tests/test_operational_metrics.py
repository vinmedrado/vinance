from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.trading.ml_engine.config import MLEngineConfig
from backend.trading.ml_engine.evaluator import operational_metrics


def test_probability_bands_count_only_tp_probability_signals() -> None:
    frame = pd.DataFrame(
        {
            "target_class": [1, 1, 0, -1, 0, -1],
            "target_value": [0.10, 0.08, 0.01, -0.03, 0.02, -0.04],
        }
    )
    labels = [-1, 0, 1]
    predictions = np.array([1, 0, 0, -1, -1, 1])
    probabilities = np.array(
        [
            [0.05, 0.10, 0.85],  # TP signal, correct
            [0.10, 0.70, 0.20],  # high confidence class 0, not TP signal
            [0.05, 0.80, 0.15],  # high confidence class 0, not TP signal
            [0.90, 0.05, 0.05],  # high confidence class -1, not TP signal
            [0.60, 0.20, 0.20],  # high confidence class -1, not TP signal
            [0.20, 0.10, 0.70],  # TP signal, wrong
        ]
    )
    config = MLEngineConfig(probability_thresholds=(0.60,))

    metrics = operational_metrics(
        frame=frame,
        predictions=predictions,
        probabilities=probabilities,
        labels=labels,
        config=config,
    )

    tp_band = metrics["probability_bands"]["0.60"]
    assert tp_band["signals"] == 2
    assert tp_band["tp_precision"] == 0.5
    assert tp_band["mean_return"] == pytest.approx(0.03)
    assert tp_band["financial_expectancy"] == pytest.approx(0.03)
    assert tp_band["predicted_tp_count"] == 2
    assert tp_band["true_tp_count"] == 2
    assert tp_band["tp_recall"] == 0.5

    confidence = metrics["confidence_all_classes"]["0.60"]
    assert confidence["signals"] == 6
    assert confidence["predicted_class_distribution"] == {"-1": 2, "0": 2, "1": 2}
