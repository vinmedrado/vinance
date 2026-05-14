
from __future__ import annotations

import json
from db import pg_compat as dbcompat
from typing import Any


def _safe_json(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _score_from_payload(payload: dict[str, Any]) -> float | None:
    score_obj = payload.get("global_intelligence_score") or {}
    if not isinstance(score_obj, dict):
        return None
    score = score_obj.get("score")
    try:
        return float(score) if score is not None else None
    except Exception:
        return None


def _label_from_payload(payload: dict[str, Any]) -> str | None:
    score_obj = payload.get("global_intelligence_score") or {}
    return score_obj.get("label") if isinstance(score_obj, dict) else None


def _metric_from_agent(payload: dict[str, Any], agent: str, metric: str) -> Any:
    agents = payload.get("agents") or {}
    if not isinstance(agents, dict):
        return None
    data = agents.get(agent) or {}
    if not isinstance(data, dict):
        return None
    metrics = data.get("metrics_used") or {}
    if not isinstance(metrics, dict):
        return None
    return metrics.get(metric)


def _safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except Exception:
        return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _extract_snapshot(row: dbcompat.Row | dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    payload = _safe_json(item.get("result_json"))

    score = _score_from_payload(payload)
    return {
        "id": item.get("id"),
        "job_id": item.get("job_id"),
        "mode": item.get("mode"),
        "status": item.get("status"),
        "started_at": item.get("started_at"),
        "finished_at": item.get("finished_at"),
        "duration_seconds": item.get("duration_seconds"),
        "payload": payload,
        "score": score,
        "label": _label_from_payload(payload),
        "top_insights_count": len(payload.get("top_insights") or []),
        "warnings_count": len(payload.get("warnings") or []),
        "opportunities_count": len(payload.get("opportunities") or []),
        "strategy_return": _safe_float(_metric_from_agent(payload, "strategy", "total_return")),
        "drawdown": _safe_float(_metric_from_agent(payload, "risk", "max_drawdown")),
        "turnover": _safe_float(_metric_from_agent(payload, "strategy", "turnover")),
        "catalog_quality": _safe_float(_metric_from_agent(payload, "catalog", "avg_quality_score")),
        "risk_level": _metric_from_agent(payload, "risk", "risk_level"),
        "overall_status": payload.get("status") or payload.get("status_final") or item.get("status"),
    }


def get_last_intelligence_runs(conn: dbcompat.Connection, limit: int = 10) -> list[dict[str, Any]]:
    """
    Retorna últimas execuções com payload de inteligência.
    Usa orchestrator_runs.result_json como fonte histórica.
    """
    conn.row_factory = dbcompat.Row
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM orchestrator_runs
            WHERE result_json IS NOT NULL
              AND result_json LIKE '%global_intelligence_score%'
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    except Exception:
        return []
    return [_extract_snapshot(r) for r in rows]


def get_previous_run(conn: dbcompat.Connection, current_run_id: int) -> dict[str, Any] | None:
    conn.row_factory = dbcompat.Row
    try:
        row = conn.execute(
            """
            SELECT *
            FROM orchestrator_runs
            WHERE id < ?
              AND result_json IS NOT NULL
              AND result_json LIKE '%global_intelligence_score%'
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(current_run_id),),
        ).fetchone()
    except Exception:
        return None
    return _extract_snapshot(row) if row else None


def calculate_score_delta(current_score: float | None, previous_score: float | None) -> float | None:
    if current_score is None or previous_score is None:
        return None
    return round(float(current_score) - float(previous_score), 2)


def _compare_numeric(
    name: str,
    current: float | None,
    previous: float | None,
    higher_is_better: bool = True,
    tolerance: float = 0.01,
) -> tuple[list[str], list[str]]:
    improved: list[str] = []
    worsened: list[str] = []
    if current is None or previous is None:
        return improved, worsened

    delta = current - previous
    if abs(delta) <= tolerance:
        return improved, worsened

    is_better = delta > 0 if higher_is_better else delta < 0
    if is_better:
        improved.append(f"{name} melhorou: {previous:.4g} → {current:.4g}.")
    else:
        worsened.append(f"{name} piorou: {previous:.4g} → {current:.4g}.")
    return improved, worsened


def compare_intelligence_runs(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if not previous:
        return {
            "previous_score": None,
            "current_score": current.get("score"),
            "score_delta": None,
            "trend": "first_run",
            "improved_areas": [],
            "worsened_areas": [],
            "summary": "Primeira execução inteligente registrada.",
        }

    current_score = current.get("score")
    previous_score = previous.get("score")
    score_delta = calculate_score_delta(current_score, previous_score)

    improved: list[str] = []
    worsened: list[str] = []

    if score_delta is not None:
        if score_delta > 2:
            improved.append(f"Score global subiu de {previous_score:.1f} para {current_score:.1f}.")
        elif score_delta < -2:
            worsened.append(f"Score global caiu de {previous_score:.1f} para {current_score:.1f}.")

    checks = [
        ("Retorno", current.get("strategy_return"), previous.get("strategy_return"), True, 0.001),
        ("Drawdown", abs(current.get("drawdown") or 0) if current.get("drawdown") is not None else None, abs(previous.get("drawdown") or 0) if previous.get("drawdown") is not None else None, False, 0.001),
        ("Turnover", current.get("turnover"), previous.get("turnover"), False, 0.01),
        ("Qualidade do catálogo", current.get("catalog_quality"), previous.get("catalog_quality"), True, 0.1),
        ("Alertas", current.get("warnings_count"), previous.get("warnings_count"), False, 0),
        ("Oportunidades", current.get("opportunities_count"), previous.get("opportunities_count"), True, 0),
    ]
    for name, cur, prev, higher_is_better, tolerance in checks:
        i, w = _compare_numeric(name, _safe_float(cur), _safe_float(prev), higher_is_better, tolerance)
        improved.extend(i)
        worsened.extend(w)

    if score_delta is None:
        trend = "stable"
    elif score_delta > 2:
        trend = "improving"
    elif score_delta < -2:
        trend = "worsening"
    else:
        trend = "stable"

    if trend == "improving":
        summary = f"Score global melhorou {score_delta:+.1f} ponto(s)."
    elif trend == "worsening":
        summary = f"Score global piorou {score_delta:+.1f} ponto(s)."
    else:
        summary = "Score global está estável em relação à execução anterior."

    if improved and worsened:
        summary += " Há avanços e regressões simultâneas."
    elif improved:
        summary += " Áreas principais melhoraram."
    elif worsened:
        summary += " Algumas áreas pioraram e merecem revisão."

    return {
        "previous_run_id": previous.get("id"),
        "current_run_id": current.get("id"),
        "previous_score": previous_score,
        "current_score": current_score,
        "score_delta": score_delta,
        "trend": trend,
        "improved_areas": improved,
        "worsened_areas": worsened,
        "summary": summary,
        "previous_label": previous.get("label"),
        "current_label": current.get("label"),
        "previous_status": previous.get("overall_status"),
        "current_status": current.get("overall_status"),
    }


def detect_trend(runs: list[dict[str, Any]]) -> str:
    scores = [r.get("score") for r in runs if r.get("score") is not None]
    if len(scores) < 3:
        return "stable"
    # runs chegam DESC; inverter para ordem cronológica
    chronological = list(reversed(scores[:5]))
    delta = chronological[-1] - chronological[0]
    if delta > 3:
        return "improving"
    if delta < -3:
        return "worsening"
    return "stable"


def build_history_for_current(conn: dbcompat.Connection, current_run_id: int) -> dict[str, Any]:
    runs = get_last_intelligence_runs(conn, 10)
    current = next((r for r in runs if int(r.get("id") or 0) == int(current_run_id)), None)
    if not current:
        try:
            row = conn.execute("SELECT * FROM orchestrator_runs WHERE id=?", (int(current_run_id),)).fetchone()
            current = _extract_snapshot(row) if row else None
        except Exception:
            current = None

    if not current:
        return {
            "previous_score": None,
            "current_score": None,
            "score_delta": None,
            "trend": "unknown",
            "improved_areas": [],
            "worsened_areas": [],
            "summary": "Histórico inteligente indisponível para esta execução.",
        }

    previous = get_previous_run(conn, int(current_run_id))
    comparison = compare_intelligence_runs(current, previous)
    comparison["multi_run_trend"] = detect_trend(runs)
    return comparison
