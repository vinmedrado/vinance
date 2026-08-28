from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.ml.dataset import latest_feature_matrix
from backend.app.intelligence.ml.model_registry import load_model


def _percentile_scores(predictions: list[float]) -> list[float]:
    if not predictions:
        return []
    ordered = sorted((value, idx) for idx, value in enumerate(predictions))
    scores = [50.0] * len(predictions)
    if len(predictions) == 1:
        return [50.0]
    for rank, (_, idx) in enumerate(ordered):
        scores[idx] = 1.0 + 99.0 * (rank / (len(predictions) - 1))
    return scores


async def predict_asset_scores(session: AsyncSession, *, market: str, limit: int = 100) -> dict[str, Any]:
    model, metadata = load_model(market=market)
    if model is None:
        return {
            "market": market,
            "model_available": False,
            "methodology": "feature_heuristic_fallback",
            "predictions": [],
            "warnings": ["Modelo ML baseline não encontrado; fallback heurístico deve ser usado."],
        }

    rows, feature_columns = await latest_feature_matrix(session, market=market, limit=limit)
    if not rows:
        return {
            "market": market,
            "model_available": True,
            "methodology": "feature_heuristic_fallback",
            "predictions": [],
            "warnings": ["Sem features recentes para inferência; fallback heurístico deve ser usado."],
        }

    x_values = [[float(row.get(column) or 0.0) for column in feature_columns] for row in rows]
    raw_predictions = [float(value) for value in model.predict(x_values)]
    score_values = _percentile_scores(raw_predictions)
    predictions = []
    for row, raw, score in zip(rows, raw_predictions, score_values, strict=False):
        predictions.append(
            {
                "ticker": row["ticker"],
                "date": row["date"],
                "prediction_return": raw,
                "prediction_score": round(score, 4),
            }
        )
    predictions.sort(key=lambda item: item["prediction_score"], reverse=True)
    return {
        "market": market,
        "model_available": True,
        "methodology": "ml_baseline",
        "predictions": predictions,
        "metadata": metadata or {},
        "warnings": [],
    }


async def rank_assets_with_model(session: AsyncSession, *, market: str, limit: int = 100) -> dict[str, float]:
    result = await predict_asset_scores(session, market=market, limit=limit)
    if not result.get("model_available") or result.get("methodology") != "ml_baseline":
        return {}
    return {str(item["ticker"]).upper(): float(item["prediction_score"]) for item in result.get("predictions", [])}
