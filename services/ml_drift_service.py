
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from services.ml_feature_service import build_features


def detect_feature_drift(baseline: pd.DataFrame, current: pd.DataFrame, features: list[str], threshold: float = 0.15) -> dict[str, Any]:
    drifted = []
    scores = {}
    for feature in features:
        if feature not in baseline.columns or feature not in current.columns:
            continue
        b = pd.to_numeric(baseline[feature], errors="coerce").dropna()
        c = pd.to_numeric(current[feature], errors="coerce").dropna()
        if len(b) < 20 or len(c) < 20:
            continue
        stat, pvalue = ks_2samp(b, c)
        scores[feature] = float(stat)
        if stat > threshold:
            drifted.append({"feature": feature, "ks_stat": float(stat), "pvalue": float(pvalue)})
    drift_score = float(np.mean(list(scores.values()))) if scores else 0.0
    action = "retrain_triggered" if drift_score > threshold and len(drifted) > max(1, len(features) * 0.3) else "ok"
    return {"drift_score": drift_score, "drifted_features": drifted, "action_taken": action}


def check_drift_for_model(model_id: int, features: list[str]) -> dict[str, Any]:
    df, warnings = build_features()
    if df.empty:
        return {"drift_score": 0, "drifted_features": [], "action_taken": "no_data", "warnings": warnings}
    ordered = df.sort_values("date")
    split = int(len(ordered) * 0.8)
    baseline = ordered.iloc[:split]
    current = ordered.iloc[split:]
    return detect_feature_drift(baseline, current, features)
