from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


VALIDATION_ENGINE_VERSION = "v2"
SUPPORTED_ASSETS = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
SUPPORTED_MODELS = (
    "hist_gradient_boosting",
    "xgboost",
    "random_forest",
    "extra_trees",
    "logistic_regression",
)


@dataclass(frozen=True)
class ValidationConfig:
    engine_version: str = VALIDATION_ENGINE_VERSION
    manifest_path: Path = Path("backend/trading/artifacts/ml_engine_v2/manifest.json")
    backtesting_output_root: Path = Path("backend/trading/output/backtesting_v2")
    research_output_root: Path = Path("backend/trading/output/research_v2")
    output_root: Path = Path("backend/trading/output/validation_v2")
    assets: tuple[str, ...] = SUPPORTED_ASSETS
    supported_models: tuple[str, ...] = SUPPORTED_MODELS
    minimum_assets_continuous: int = 2
    minimum_targets_continuous: int = 2
    minimum_models_continuous: int = 2
    minimum_periods_continuous: int = 2
    minimum_oos_windows: int = 3
    minimum_case_score: float = 60.0
    minimum_continuous_score: float = 75.0
    overwrite: bool = True
    paper_only: bool = True

    def __post_init__(self) -> None:
        if not self.paper_only:
            raise RuntimeError("Validation V2 requires PAPER_ONLY=True.")
        if not self.assets:
            raise ValueError("assets must not be empty")
        if not self.supported_models:
            raise ValueError("supported_models must not be empty")
        for value in (
            self.minimum_assets_continuous,
            self.minimum_targets_continuous,
            self.minimum_models_continuous,
            self.minimum_periods_continuous,
            self.minimum_oos_windows,
        ):
            if value < 1:
                raise ValueError("validation minimum counts must be positive")
        for value in (self.minimum_case_score, self.minimum_continuous_score):
            if not 0 <= value <= 100:
                raise ValueError("validation scores must be between 0 and 100")

    def deterministic_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "manifest_path",
            "backtesting_output_root",
            "research_output_root",
            "output_root",
            "overwrite",
        ):
            payload.pop(key, None)
        return payload
