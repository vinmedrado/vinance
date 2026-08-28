from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SupportedMLMarket = Literal["acoes", "fii", "cripto"]


class TrainMLRequest(BaseModel):
    market: SupportedMLMarket = "acoes"
    horizon_days: int = Field(default=90, ge=30, le=180)
    min_samples: int = Field(default=30, ge=10, le=5000)


class PredictMLRequest(BaseModel):
    market: SupportedMLMarket = "acoes"
    limit: int = Field(default=20, ge=1, le=100)


class MLTrainResponse(BaseModel):
    market: str
    horizon_days: int
    trained: bool
    sample_size: int
    model_path: str | None = None
    metadata_path: str | None = None
    model_metrics: dict[str, Any] = Field(default_factory=dict)
    baseline_metrics: dict[str, Any] = Field(default_factory=dict)
    feature_importance: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)


class MLPredictResponse(BaseModel):
    market: str
    model_available: bool
    methodology: str
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MLStatusResponse(BaseModel):
    artifacts_dir: str
    models: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
