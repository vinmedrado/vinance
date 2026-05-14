
from __future__ import annotations

from typing import Any
import pandas as pd
import numpy as np

from services.ml_common import (
    DATASETS_DIR, bootstrap_ml_tables, connect, json_dump, now_iso,
    start_ml_run, finish_ml_run
)
from services.ml_feature_service import build_features

FEATURE_COLUMNS = [
    "return_5d", "return_21d", "return_63d",
    "volatility_21d", "volatility_63d", "drawdown_63d",
    "distance_mm50", "distance_mm200", "trend_strength",
    "avg_volume_21d", "avg_volume_63d", "data_quality_score",
]

VALID_TARGETS = {"future_return_positive", "future_return_regression", "future_return_class"}


def _apply_quality_filters(df: pd.DataFrame, min_quality_score: float = 45, min_history_days: int = 180) -> tuple[pd.DataFrame, dict[str, Any]]:
    before = len(df)
    tickers_before = df["ticker"].nunique() if "ticker" in df.columns else 0

    # Histórico por ticker em dias entre primeira e última data.
    hist = df.groupby("ticker")["date"].agg(["min", "max", "count"]).reset_index()
    hist["history_days"] = (hist["max"] - hist["min"]).dt.days
    allowed_history = set(hist.loc[hist["history_days"] >= int(min_history_days), "ticker"].astype(str))

    df = df[df["ticker"].astype(str).isin(allowed_history)].copy()
    removed_history = before - len(df)

    removed_quality = 0
    if "data_quality_score" in df.columns:
        before_q = len(df)
        df = df[pd.to_numeric(df["data_quality_score"], errors="coerce").fillna(0) >= float(min_quality_score)].copy()
        removed_quality = before_q - len(df)

    meta = {
        "rows_before_filters": before,
        "rows_after_filters": len(df),
        "tickers_before_filters": int(tickers_before),
        "tickers_after_filters": int(df["ticker"].nunique()) if "ticker" in df.columns else 0,
        "rows_removed_by_quality_filter": int(removed_quality),
        "rows_removed_by_history_filter": int(removed_history),
        "min_quality_score": float(min_quality_score),
        "min_history_days": int(min_history_days),
    }
    return df, meta


def build_dataset(
    asset_class: str = "all",
    start_date: str | None = None,
    end_date: str | None = None,
    target: str = "future_return_positive",
    horizon_days: int = 21,
    min_quality_score: float = 45,
    min_history_days: int = 180,
) -> dict[str, Any]:
    if target not in VALID_TARGETS:
        raise ValueError(f"Target inválido: {target}. Use {sorted(VALID_TARGETS)}")

    params = {
        "asset_class": asset_class,
        "start_date": start_date,
        "end_date": end_date,
        "target": target,
        "horizon_days": horizon_days,
        "min_quality_score": min_quality_score,
        "min_history_days": min_history_days,
    }

    with connect() as conn:
        bootstrap_ml_tables(conn)
        run_id = start_ml_run(conn, "build_dataset", params)
        try:
            df, warnings = build_features(asset_class=asset_class, start_date=start_date, end_date=end_date)
            if df.empty:
                raise RuntimeError("Sem dados suficientes para construir dataset.")

            df, filter_meta = _apply_quality_filters(df, min_quality_score=min_quality_score, min_history_days=min_history_days)
            if df.empty:
                raise RuntimeError("Dataset vazio após filtros de qualidade/histórico.")

            frames = []
            for ticker, g in df.groupby("ticker", dropna=False):
                g = g.sort_values("date").copy()
                g["future_close"] = g["close"].shift(-int(horizon_days))
                g["future_return"] = (g["future_close"] / g["close"]) - 1
                g["future_return_positive"] = (g["future_return"] > 0).astype(int)
                g["future_return_regression"] = g["future_return"]
                g["future_return_class"] = pd.cut(
                    g["future_return"],
                    bins=[-np.inf, 0, 0.05, np.inf],
                    labels=["low", "medium", "high"],
                    include_lowest=True,
                ).astype(str)
                frames.append(g)

            out = pd.concat(frames, ignore_index=True).dropna(subset=["future_return"])
            if out.empty:
                raise RuntimeError("Dataset vazio após cálculo do target futuro.")

            for col in FEATURE_COLUMNS:
                if col not in out.columns:
                    out[col] = 0
                out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

            keep_cols = [
                "ticker", "date", "asset_class", "future_return",
                "future_return_positive", "future_return_regression", "future_return_class",
                *FEATURE_COLUMNS,
            ]
            out = out[[c for c in keep_cols if c in out.columns]].copy()
            name = f"dataset_{asset_class}_{target}_{now_iso().replace(':','-')}.csv"
            path = DATASETS_DIR / name
            out.to_csv(path, index=False)

            metadata = {
                "path": str(path),
                "warnings": warnings,
                "horizon_days": horizon_days,
                "feature_columns": FEATURE_COLUMNS,
                "target_type": "regression" if target == "future_return_regression" else "classification",
                **filter_meta,
            }

            cur = conn.execute(
                """
                INSERT INTO ml_datasets (
                    name, asset_class, start_date, end_date, target_name,
                    rows_count, features_count, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name, asset_class, start_date, end_date, target,
                    int(len(out)), int(len(FEATURE_COLUMNS)), now_iso(), json_dump(metadata),
                ),
            )
            dataset_id = int(cur.lastrowid)
            conn.commit()
            result = {
                "dataset_id": dataset_id,
                "path": str(path),
                "rows": int(len(out)),
                "features": len(FEATURE_COLUMNS),
                "target": target,
                "warnings": warnings,
                **filter_meta,
            }
            finish_ml_run(conn, run_id, "success", result)
            return result
        except Exception as exc:
            finish_ml_run(conn, run_id, "failed", {}, str(exc))
            raise


def list_datasets(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        rows = conn.execute("SELECT * FROM ml_datasets ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def get_dataset(dataset_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        row = conn.execute("SELECT * FROM ml_datasets WHERE id=?", (int(dataset_id),)).fetchone()
        return dict(row) if row else None


def load_dataset_dataframe(dataset_id: int) -> pd.DataFrame:
    ds = get_dataset(dataset_id)
    if not ds:
        raise ValueError("Dataset não encontrado.")
    import json
    meta = json.loads(ds.get("metadata_json") or "{}")
    path = meta.get("path")
    if not path:
        path = str(DATASETS_DIR / ds["name"])
    df = pd.read_csv(path)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df
