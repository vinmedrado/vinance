from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.intelligence.ml.dataset import build_supervised_dataset
from backend.app.intelligence.ml.evaluate import regression_metrics
from backend.app.intelligence.ml.model_registry import save_model

SUPPORTED_TRAIN_MARKETS = {"acoes", "fii", "cripto"}


def _heuristic_predictions(rows: list[dict[str, Any]]) -> list[float]:
    # score_final is 0-100 and remains the fallback baseline. Normalize around 50
    # so it can be compared with future returns as a ranking proxy, not as a
    # calibrated return predictor.
    values: list[float] = []
    for row in rows:
        score = row.get("score_final")
        values.append(((float(score) if score is not None else 50.0) - 50.0) / 100.0)
    return values


def _feature_importance(model: Any, columns: list[str]) -> dict[str, float]:
    values = getattr(model, "feature_importances_", None)
    if values is None:
        return {}
    return {column: float(value) for column, value in zip(columns, values, strict=False)}


async def train_market_model(
    session: AsyncSession,
    *,
    market: str,
    horizon_days: int = 90,
    min_samples: int = 30,
) -> dict[str, Any]:
    if market not in SUPPORTED_TRAIN_MARKETS:
        return {
            "market": market,
            "horizon_days": horizon_days,
            "trained": False,
            "sample_size": 0,
            "warnings": [f"Mercado {market} ainda não suportado no baseline ML inicial."],
            "methodology": ["ETFs/BDRs permanecem para fase futura por dependência de histórico suficiente."],
        }

    dataset = await build_supervised_dataset(session, market=market, horizon_days=horizon_days)
    if dataset.sample_size < min_samples:
        return {
            "market": market,
            "horizon_days": horizon_days,
            "trained": False,
            "sample_size": dataset.sample_size,
            "warnings": [
                f"Amostra insuficiente para treino: {dataset.sample_size}/{min_samples} registros válidos.",
                *dataset.warnings[:25],
            ],
            "methodology": [
                "Dataset supervisionado usa features na data t e retorno futuro como target.",
                "Treino não executado para evitar modelo frágil com amostra insuficiente.",
            ],
        }

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split
    except ImportError as exc:  # pragma: no cover - environment guard
        return {
            "market": market,
            "horizon_days": horizon_days,
            "trained": False,
            "sample_size": dataset.sample_size,
            "warnings": [f"scikit-learn indisponível: {exc}"],
            "methodology": ["Fallback heurístico permanece ativo quando ML não pode ser treinado."],
        }

    x_values, y_values, _ = dataset.to_xy()
    # Chronological split preserves temporal ordering better than random sampling
    # and reduces leakage risk for a baseline model.
    split_index = max(1, int(len(x_values) * 0.8))
    if split_index >= len(x_values):
        split_index = len(x_values) - 1
    x_train, x_test = x_values[:split_index], x_values[split_index:]
    y_train, y_test = y_values[:split_index], y_values[split_index:]

    model = RandomForestRegressor(n_estimators=120, max_depth=6, min_samples_leaf=3, random_state=42, n_jobs=1)
    model.fit(x_train, y_train)
    predictions = [float(value) for value in model.predict(x_test)] if x_test else []
    heuristic = _heuristic_predictions(dataset.rows[split_index:]) if x_test else []

    model_metrics = regression_metrics(y_test, predictions)
    baseline_metrics = regression_metrics(y_test, heuristic)
    trained_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "trained_at": trained_at,
        "model_type": "RandomForestRegressor",
        "target": f"future_return_{horizon_days}d",
        "sample_size": dataset.sample_size,
        "train_size": len(x_train),
        "test_size": len(x_test),
        "feature_columns": dataset.feature_columns,
        "model_metrics": model_metrics,
        "baseline_metrics": baseline_metrics,
        "feature_importance": _feature_importance(model, dataset.feature_columns),
        "notes": [
            "Baseline supervisionado; não é recomendação definitiva de compra.",
            "Features são calculadas antes do target; target usa preço futuro posterior à data da feature.",
            "Sem LSTM, Prophet, deep learning ou backtest operacional nesta fase.",
        ],
    }
    paths = save_model(model, market=market, horizon_days=horizon_days, metadata=metadata)
    return {
        "market": market,
        "horizon_days": horizon_days,
        "trained": True,
        "sample_size": dataset.sample_size,
        "model_path": paths["model_path"],
        "metadata_path": paths["metadata_path"],
        "model_metrics": model_metrics,
        "baseline_metrics": baseline_metrics,
        "feature_importance": metadata["feature_importance"],
        "warnings": dataset.warnings[:25],
        "methodology": metadata["notes"],
    }


async def train_all_baselines(session: AsyncSession, *, horizon_days: int = 90, min_samples: int = 30) -> dict[str, Any]:
    results = []
    for market in ("acoes", "fii", "cripto"):
        results.append(await train_market_model(session, market=market, horizon_days=horizon_days, min_samples=min_samples))
    return {"results": results, "trained": sum(1 for item in results if item.get("trained"))}
