
from __future__ import annotations

from typing import Any
from services.ml_common import bootstrap_ml_tables, connect, json_load


def list_models(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        rows = conn.execute("SELECT * FROM ml_models ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def get_model(model_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        row = conn.execute("SELECT * FROM ml_models WHERE id=?", (int(model_id),)).fetchone()
        return dict(row) if row else None


def get_best_model(asset_class: str | None = None, target_name: str | None = None) -> dict[str, Any] | None:
    models = list_models(500)
    best = None
    best_score = -1
    for model in models:
        if asset_class and model.get("asset_class") != asset_class:
            continue
        if target_name and model.get("target_name") != target_name:
            continue
        metrics = json_load(model.get("metrics_json"))
        score = metrics.get("roc_auc")
        if score is None:
            score = metrics.get("f1")
        try:
            score = float(score)
        except Exception:
            score = -1
        if score > best_score:
            best_score = score
            best = model
    return best


def list_predictions(model_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        if model_id:
            rows = conn.execute(
                "SELECT * FROM ml_predictions WHERE model_id=? ORDER BY prediction_date DESC, predicted_score DESC LIMIT ?",
                (int(model_id), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ml_predictions ORDER BY prediction_date DESC, predicted_score DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]


def ml_overview() -> dict[str, Any]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        datasets = conn.execute("SELECT COUNT(*) AS total FROM ml_datasets").fetchone()["total"]
        models = conn.execute("SELECT COUNT(*) AS total FROM ml_models").fetchone()["total"]
        predictions = conn.execute("SELECT COUNT(*) AS total FROM ml_predictions").fetchone()["total"]
        last_model = conn.execute("SELECT * FROM ml_models ORDER BY id DESC LIMIT 1").fetchone()
        return {
            "datasets": int(datasets or 0),
            "models": int(models or 0),
            "predictions": int(predictions or 0),
            "last_model": dict(last_model) if last_model else None,
            "best_model": get_best_model(),
        }
