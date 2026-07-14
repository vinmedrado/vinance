from __future__ import annotations

from .config import DEFAULT_CONFIG, PredictionEngineConfig
from .errors import PredictionArtifactError, PredictionCompatibilityError, PredictionEngineError, PredictionFeatureError
from .models import LoadedArtifacts, ManifestEntry, PredictionInput, PredictionProbabilities, PredictionResult

__all__ = [
    "DEFAULT_CONFIG",
    "LoadedArtifacts",
    "ManifestEntry",
    "PredictionArtifactError",
    "PredictionCompatibilityError",
    "PredictionEngine",
    "PredictionEngineConfig",
    "PredictionEngineError",
    "PredictionFeatureError",
    "PredictionInput",
    "PredictionProbabilities",
    "PredictionResult",
]


def __getattr__(name: str):
    if name == "PredictionEngine":
        from .pipeline import PredictionEngine

        return PredictionEngine
    raise AttributeError(name)
