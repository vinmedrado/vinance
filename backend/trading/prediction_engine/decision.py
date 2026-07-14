from __future__ import annotations

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .models import PredictionProbabilities


BUY_CANDIDATE = "BUY_CANDIDATE"
HOLD = "HOLD"
AVOID = "AVOID"
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
VERY_HIGH = "VERY_HIGH"


def decide(probabilities: PredictionProbabilities, config: PredictionEngineConfig = DEFAULT_CONFIG) -> str:
    if probabilities.probability_stop_loss >= config.stop_loss_threshold:
        return AVOID
    if probabilities.probability_take_profit >= config.take_profit_threshold:
        return BUY_CANDIDATE
    return HOLD


def confidence_level(confidence: float) -> str:
    if confidence >= 0.85:
        return VERY_HIGH
    if confidence >= 0.70:
        return HIGH
    if confidence >= 0.55:
        return MEDIUM
    return LOW
