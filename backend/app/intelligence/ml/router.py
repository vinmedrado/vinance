from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.intelligence.ml.inference import predict_asset_scores
from backend.app.intelligence.ml.model_registry import ARTIFACTS_DIR, list_model_metadata
from backend.app.intelligence.ml.schemas import MLPredictResponse, MLStatusResponse, PredictMLRequest, TrainMLRequest, MLTrainResponse
from backend.app.intelligence.ml.train import train_market_model

router = APIRouter(prefix="/ml", tags=["intelligence-ml"])


@router.post("/train", response_model=MLTrainResponse)
async def train_model(
    payload: TrainMLRequest,
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - auth guard
    session: AsyncSession = Depends(get_session),
):
    return await train_market_model(
        session,
        market=payload.market,
        horizon_days=payload.horizon_days,
        min_samples=payload.min_samples,
    )


@router.get("/status", response_model=MLStatusResponse)
async def status(current_user: User = Depends(get_current_user)):  # noqa: ARG001 - auth guard
    return {
        "artifacts_dir": str(ARTIFACTS_DIR),
        "models": list_model_metadata(),
        "warnings": ["ML baseline é experimental e não substitui o fallback heurístico."],
    }


@router.post("/predict", response_model=MLPredictResponse)
async def predict(
    payload: PredictMLRequest,
    current_user: User = Depends(get_current_user),  # noqa: ARG001 - auth guard
    session: AsyncSession = Depends(get_session),
):
    return await predict_asset_scores(session, market=payload.market, limit=payload.limit)
