from __future__ import annotations


class PredictionEngineError(RuntimeError):
    pass


class PredictionCompatibilityError(PredictionEngineError):
    def __init__(self, *, dependency: str, expected: str, found: str, model_name: str) -> None:
        super().__init__(
            f"Incompatible {dependency} version for model {model_name}: "
            f"expected {expected}, found {found}."
        )
        self.dependency = dependency
        self.expected = expected
        self.found = found
        self.model_name = model_name


class PredictionArtifactError(PredictionEngineError):
    pass


class PredictionFeatureError(PredictionEngineError):
    pass
