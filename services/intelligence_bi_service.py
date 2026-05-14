
from __future__ import annotations

import json
from db import pg_compat as dbcompat
from typing import Any

import pandas as pd


def _safe_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except Exception:
        return 0


def load_intelligence_history(conn: dbcompat.Connection, limit: int | None = None) -> list[dict[str, Any]]:
    """
    Lê histórico inteligente a partir de orchestrator_runs.result_json.
    Não altera banco, não cria tabela e suporta registros antigos incompletos.
    """
    conn.row_factory = dbcompat.Row
    sql = """
        SELECT id, job_id, mode, status, started_at, finished_at, duration_seconds, result_json
        FROM orchestrator_runs
        WHERE result_json IS NOT NULL
          AND (
            result_json LIKE '%global_intelligence_score%'
            OR result_json LIKE '%intelligence_history%'
            OR result_json LIKE '%agents%'
          )
        ORDER BY id ASC
    """
    args: list[Any] = []
    if limit:
        sql += " LIMIT ?"
        args.append(int(limit))
    try:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def build_intelligence_dataframe(runs: list[dict[str, Any]]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    previous_score: float | None = None

    for row in runs:
        payload = _safe_json(row.get("result_json"))
        score_obj = payload.get("global_intelligence_score") or {}
        hist = payload.get("intelligence_history") or {}
        if not isinstance(score_obj, dict):
            score_obj = {}
        if not isinstance(hist, dict):
            hist = {}

        score = _safe_float(score_obj.get("score"))
        delta = _safe_float(hist.get("score_delta"))
        if delta is None and score is not None and previous_score is not None:
            delta = round(score - previous_score, 2)

        trend = hist.get("trend")
        if not trend:
            if delta is None:
                trend = "first_run"
            elif delta > 2:
                trend = "improving"
            elif delta < -2:
                trend = "worsening"
            else:
                trend = "stable"

        top_insights = payload.get("top_insights") or []
        warnings = payload.get("warnings") or []
        opportunities = payload.get("opportunities") or []

        record = {
            "run_id": row.get("id"),
            "job_id": row.get("job_id"),
            "mode": row.get("mode"),
            "status": row.get("status"),
            "data": row.get("started_at"),
            "finished_at": row.get("finished_at"),
            "duration_seconds": row.get("duration_seconds"),
            "score": score,
            "delta": delta,
            "trend": trend,
            "label": score_obj.get("label"),
            "alertas": len(top_insights) + len(warnings),
            "top_insights": len(top_insights),
            "warnings": len(warnings),
            "oportunidades": len(opportunities),
            "resumo": hist.get("summary") or payload.get("final_explanation") or payload.get("final_message") or "",
            "previous_score": hist.get("previous_score"),
            "current_score": hist.get("current_score") or score,
        }
        records.append(record)

        if score is not None:
            previous_score = score

    df = pd.DataFrame(records)
    if df.empty:
        return df

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["delta"] = pd.to_numeric(df["delta"], errors="coerce").fillna(0)
    df["alertas"] = pd.to_numeric(df["alertas"], errors="coerce").fillna(0).astype(int)
    df["warnings"] = pd.to_numeric(df["warnings"], errors="coerce").fillna(0).astype(int)
    df["oportunidades"] = pd.to_numeric(df["oportunidades"], errors="coerce").fillna(0).astype(int)
    df["run_id"] = pd.to_numeric(df["run_id"], errors="coerce").astype("Int64")
    return df


def calculate_moving_average(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    if df.empty or "score" not in df.columns:
        return df
    out = df.sort_values("data").copy()
    out[f"ma_{window}"] = out["score"].rolling(window=window, min_periods=1).mean()
    return out


def calculate_bi_kpis(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "last_score": None,
            "last_delta": None,
            "current_trend": None,
            "best_score": None,
            "worst_score": None,
            "avg_last_5": None,
            "total_runs": 0,
        }

    ordered = df.sort_values("data")
    last = ordered.iloc[-1]
    return {
        "last_score": None if pd.isna(last.get("score")) else round(float(last.get("score")), 2),
        "last_delta": None if pd.isna(last.get("delta")) else round(float(last.get("delta")), 2),
        "current_trend": last.get("trend"),
        "best_score": None if ordered["score"].dropna().empty else round(float(ordered["score"].max()), 2),
        "worst_score": None if ordered["score"].dropna().empty else round(float(ordered["score"].min()), 2),
        "avg_last_5": None if ordered["score"].dropna().empty else round(float(ordered["score"].tail(5).mean()), 2),
        "total_runs": int(len(ordered)),
    }


def prepare_trend_distribution(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "trend" not in df.columns:
        return pd.DataFrame(columns=["trend", "count"])
    return df.groupby("trend", dropna=False).size().reset_index(name="count")


def prepare_alerts_series(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["data", "alertas"])
    return df[["data", "alertas", "warnings", "top_insights"]].copy()


def prepare_opportunities_series(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["data", "oportunidades"])
    return df[["data", "oportunidades"]].copy()


def build_executive_reading(df: pd.DataFrame, kpis: dict[str, Any]) -> str:
    if df.empty or int(kpis.get("total_runs") or 0) == 0:
        return "Ainda não há histórico inteligente suficiente. Rode o Orquestrador Geral para gerar dados."

    trend = kpis.get("current_trend")
    last_score = kpis.get("last_score")
    last_delta = kpis.get("last_delta")
    avg_last_5 = kpis.get("avg_last_5")

    alerts_recent = int(df.sort_values("data").tail(3)["alertas"].sum()) if "alertas" in df.columns else 0

    if trend == "improving":
        msg = f"O score global está em tendência de melhora. Último score: {last_score}, delta: {last_delta:+.1f}."
    elif trend == "worsening":
        msg = f"O score global está piorando. Último score: {last_score}, delta: {last_delta:+.1f}. Revise alertas recentes."
    elif trend == "stable":
        msg = f"A inteligência está estável. Último score: {last_score}; média dos últimos registros: {avg_last_5}."
    elif trend == "first_run":
        msg = "Primeira execução inteligente registrada. Novas execuções permitirão análise de tendência."
    else:
        msg = f"Histórico inteligente carregado. Último score: {last_score}."

    if alerts_recent >= 5:
        msg += " Os alertas permanecem elevados nas últimas execuções."
    elif alerts_recent == 0:
        msg += " Não há alertas recentes relevantes."

    return msg
