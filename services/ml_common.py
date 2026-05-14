
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from services.db_session import db_session

ROOT = Path(__file__).resolve().parents[1]
ML_DIR = ROOT / "ml"
DATASETS_DIR = ML_DIR / "datasets"
MODELS_DIR = ML_DIR / "models"
PREDICTIONS_DIR = ML_DIR / "predictions"
REPORTS_DIR = ML_DIR / "reports"

for _d in (DATASETS_DIR, MODELS_DIR, PREDICTIONS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def connect():
    """
    Compatibilidade transitória: retorna Session SQLAlchemy.
    Novo código deve usar `with db_session() as db:`.
    """
    return db_session()


def json_dump(value: Any) -> str:
    try:
        return json.dumps(value or {}, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def json_load(raw: str | None) -> Any:
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def table_exists(db, name: str) -> bool:
    row = db.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema='public' AND table_name=:name
            ) AS exists
        """),
        {"name": name},
    ).mappings().first()
    return bool(row["exists"]) if row else False


def table_columns(db, name: str) -> list[str]:
    if not table_exists(db, name):
        return []
    rows = db.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:name
            ORDER BY ordinal_position
        """),
        {"name": name},
    ).mappings().all()
    return [r["column_name"] for r in rows]


def first_existing(cols: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in cols:
            return c
    return None


def bootstrap_ml_tables(db=None) -> None:
    close_after = False
    if db is None:
        ctx = db_session()
        db = ctx.__enter__()
        close_after = True
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_datasets (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                name TEXT,
                asset_class TEXT,
                start_date TEXT,
                end_date TEXT,
                target_name TEXT,
                rows_count INTEGER,
                features_count INTEGER,
                created_at TEXT,
                metadata_json TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_models (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                dataset_id INTEGER,
                model_name TEXT,
                model_type TEXT,
                target_name TEXT,
                asset_class TEXT,
                train_start TEXT,
                train_end TEXT,
                test_start TEXT,
                test_end TEXT,
                metrics_json TEXT,
                feature_importance_json TEXT,
                model_path TEXT,
                status TEXT,
                created_at TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_predictions (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                model_id INTEGER,
                ticker TEXT,
                prediction_date TEXT,
                predicted_score REAL,
                predicted_label TEXT,
                confidence REAL,
                features_json TEXT,
                explanation_json TEXT,
                created_at TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_runs (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                run_type TEXT,
                status TEXT,
                started_at TEXT,
                finished_at TEXT,
                duration_seconds REAL,
                parameters_json TEXT,
                result_json TEXT,
                error_message TEXT
            )
        """))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_model_evaluations (
                id SERIAL PRIMARY KEY,
                tenant_id UUID,
                model_id INTEGER,
                evaluation_date TEXT,
                split_mode TEXT,
                target_name TEXT,
                metrics_json TEXT,
                created_at TEXT
            )
        """))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_predictions_model ON ml_predictions(model_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_predictions_tenant ON ml_predictions(tenant_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_ml_models_dataset ON ml_models(dataset_id)"))
        db.commit()
    finally:
        if close_after:
            ctx.__exit__(None, None, None)


def start_ml_run(db, run_type: str, params: dict[str, Any], tenant_id: str | None = None) -> int:
    started = now_iso()
    row = db.execute(
        text("""
            INSERT INTO ml_runs (tenant_id, run_type, status, started_at, parameters_json, result_json)
            VALUES (:tenant_id, :run_type, 'running', :started_at, :params, '{}')
            RETURNING id
        """),
        {"tenant_id": tenant_id, "run_type": run_type, "started_at": started, "params": json_dump(params)},
    ).mappings().first()
    db.commit()
    return int(row["id"])


def finish_ml_run(db, run_id: int, status: str, result: dict[str, Any], error: str | None = None) -> None:
    finished = now_iso()
    row = db.execute(text("SELECT started_at FROM ml_runs WHERE id=:id"), {"id": int(run_id)}).mappings().first()
    duration = None
    if row and row["started_at"]:
        try:
            duration = (datetime.fromisoformat(finished) - datetime.fromisoformat(row["started_at"])).total_seconds()
        except Exception:
            duration = None
    db.execute(
        text("""
            UPDATE ml_runs
            SET status=:status, finished_at=:finished_at, duration_seconds=:duration,
                result_json=:result_json, error_message=:error
            WHERE id=:id
        """),
        {
            "status": status,
            "finished_at": finished,
            "duration": duration,
            "result_json": json_dump(result),
            "error": error,
            "id": int(run_id),
        },
    )
    db.commit()
