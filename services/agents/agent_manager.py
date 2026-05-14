
from __future__ import annotations

import json
from db import pg_compat as dbcompat
from pathlib import Path
from typing import Any

from services.intelligence_history_service import build_history_for_current

from services.agents.agent_analyst import AnalystAgent
from services.agents.agent_catalog import CatalogAgent
from services.agents.agent_explainer import ExplainerAgent
from services.agents.agent_risk import RiskAgent
from services.agents.agent_strategy import StrategyAgent

ROOT = Path(__file__).resolve().parents[2]
ROOT_DIR = ROOT / "data" / "POSTGRES_RUNTIME_DISABLED"


AGENTS = {
    "catalog": CatalogAgent,
    "strategy": StrategyAgent,
    "risk": RiskAgent,
    "analyst": AnalystAgent,
    "explainer": ExplainerAgent,
}


def _connect() -> dbcompat.Connection:
    conn = dbcompat.connect(ROOT_DIR, timeout=30, check_same_thread=False)
    conn.row_factory = dbcompat.Row
    return conn


def _table_exists(conn: dbcompat.Connection, name: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def _safe_scalar(conn: dbcompat.Connection, sql: str, default: Any = None) -> Any:
    try:
        row = conn.execute(sql).fetchone()
        return row[0] if row else default
    except Exception:
        return default


def _safe_rows(conn: dbcompat.Connection, sql: str, limit: int = 20) -> list[dict[str, Any]]:
    try:
        return [dict(r) for r in conn.execute(sql).fetchmany(limit)]
    except Exception:
        return []


def collect_context(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    context: dict[str, Any] = dict(extra or {})
    if not ROOT_DIR.exists():
        context["database"] = {"exists": False, "path": str(ROOT_DIR)}
        return context

    with _connect() as conn:
        context["database"] = {"exists": True, "path": str(ROOT_DIR)}

        orchestrator = {}
        if _table_exists(conn, "orchestrator_runs"):
            last = conn.execute("SELECT * FROM orchestrator_runs ORDER BY id DESC LIMIT 1").fetchone()
            if last:
                orchestrator = dict(last)
                try:
                    result = json.loads(orchestrator.get("result_json") or "{}")
                    orchestrator["result"] = result
                    if isinstance(result, dict):
                        orchestrator.update({
                            "status": result.get("status") or orchestrator.get("status"),
                            "status_final": result.get("status_final") or result.get("status"),
                            "success_steps": result.get("success_steps"),
                            "failed_steps": result.get("failed_steps"),
                            "warning_steps": result.get("warning_steps"),
                        })
                except Exception:
                    pass
        context["orchestrator"] = {**orchestrator, **(context.get("orchestrator") or {})}

        catalog: dict[str, Any] = {}
        table_name = "asset_catalog" if _table_exists(conn, "asset_catalog") else "assets" if _table_exists(conn, "assets") else None
        if table_name:
            catalog["total_assets"] = _safe_scalar(conn, f"SELECT COUNT(*) FROM {table_name}", 0)
            columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
            score_col = next((c for c in ("quality_score", "score_quality", "data_quality_score", "quality") if c in columns), None)
            if score_col:
                catalog["avg_quality_score"] = _safe_scalar(conn, f"SELECT AVG({score_col}) FROM {table_name}", None)
                catalog["low_quality_assets"] = _safe_scalar(conn, f"SELECT COUNT(*) FROM {table_name} WHERE {score_col} < 50", 0)
                name_col = "ticker" if "ticker" in columns else "symbol" if "symbol" in columns else "name" if "name" in columns else None
                if name_col:
                    catalog["top_quality_assets"] = _safe_rows(conn, f"SELECT {name_col}, {score_col} FROM {table_name} ORDER BY {score_col} DESC LIMIT 10", 10)
                    catalog["low_quality_asset_list"] = _safe_rows(conn, f"SELECT {name_col}, {score_col} FROM {table_name} WHERE {score_col} < 50 ORDER BY {score_col} ASC LIMIT 10", 10)
        context["catalog"] = {**catalog, **(context.get("catalog") or {})}

        coverage: dict[str, Any] = {}
        if _table_exists(conn, "assets"):
            coverage["total_assets"] = _safe_scalar(conn, "SELECT COUNT(*) FROM assets", 0)
        if _table_exists(conn, "asset_prices"):
            coverage["price_rows"] = _safe_scalar(conn, "SELECT COUNT(*) FROM asset_prices", 0)
            coverage["assets_with_price"] = _safe_scalar(conn, "SELECT COUNT(DISTINCT asset_id) FROM asset_prices WHERE asset_id IS NOT NULL", 0)
        context["coverage"] = {**coverage, **(context.get("coverage") or {})}

        backtest: dict[str, Any] = {}
        if _table_exists(conn, "backtest_metrics"):
            metrics_cols = [r["name"] for r in conn.execute("PRAGMA table_info(backtest_metrics)").fetchall()]
            cols = [c for c in ("total_return", "max_drawdown", "sharpe_ratio", "volatility", "turnover", "total_trades") if c in metrics_cols]
            if cols:
                rows = _safe_rows(conn, f"SELECT {', '.join(cols)} FROM backtest_metrics ORDER BY rowid DESC LIMIT 1", 1)
                backtest = rows[0] if rows else {}
        context["backtest"] = {**backtest, **(context.get("backtest") or {})}

        strategy = {"name": "multi_factor"}
        if _table_exists(conn, "backtest_runs"):
            run_cols = [r["name"] for r in conn.execute("PRAGMA table_info(backtest_runs)").fetchall()]
            if "strategy_name" in run_cols:
                last_strategy = _safe_scalar(conn, "SELECT strategy_name FROM backtest_runs ORDER BY id DESC LIMIT 1", None)
                if last_strategy:
                    strategy["name"] = last_strategy
        context["strategy"] = {**strategy, **(context.get("strategy") or {})}

    return context


def run_agent(name: str, context: dict[str, Any]) -> dict[str, Any]:
    if name not in AGENTS:
        raise ValueError(f"Agente desconhecido: {name}")
    return AGENTS[name]().run(context)


def _agent_score(output: dict[str, Any]) -> float | None:
    score = output.get("score")
    if isinstance(score, (int, float)):
        return max(0, min(100, float(score)))
    return None


def calculate_global_intelligence_score(agent_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    score = 50.0
    drivers: list[str] = []
    penalties: list[str] = []

    catalog = agent_outputs.get("catalog") or {}
    strategy = agent_outputs.get("strategy") or {}
    risk = agent_outputs.get("risk") or {}
    analyst = agent_outputs.get("analyst") or {}

    catalog_score = _agent_score(catalog)
    strategy_score = _agent_score(strategy)
    risk_score = _agent_score(risk)
    analyst_score = _agent_score(analyst)

    if catalog_score is not None:
        delta = (catalog_score - 50) * 0.20
        score += delta
        (drivers if delta >= 0 else penalties).append(f"Catálogo contribuiu {delta:+.1f} ponto(s).")
    if strategy_score is not None:
        delta = (strategy_score - 50) * 0.25
        score += delta
        (drivers if delta >= 0 else penalties).append(f"Estratégia contribuiu {delta:+.1f} ponto(s).")
    if risk_score is not None:
        delta = (risk_score - 50) * 0.30
        score += delta
        (drivers if delta >= 0 else penalties).append(f"Risco contribuiu {delta:+.1f} ponto(s).")
    if analyst_score is not None:
        delta = (analyst_score - 50) * 0.25
        score += delta
        (drivers if delta >= 0 else penalties).append(f"Estado operacional contribuiu {delta:+.1f} ponto(s).")

    for name, output in agent_outputs.items():
        status = output.get("status")
        if status == "critical":
            score -= 15
            penalties.append(f"{name}: status crítico.")
        elif status == "warning":
            score -= 7
            penalties.append(f"{name}: requer atenção.")

    score = round(max(0, min(100, score)), 1)
    if score >= 85:
        label = "Excelente"
    elif score >= 70:
        label = "Bom"
    elif score >= 50:
        label = "Atenção"
    else:
        label = "Crítico"

    return {"score": score, "label": label, "drivers": drivers, "penalties": penalties}


def consolidate_insights(agent_outputs: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    high, medium, low = [], [], []
    for agent_name, output in agent_outputs.items():
        for item in output.get("insights") or []:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            item.setdefault("agent", agent_name)
            priority = item.get("priority") or "medium"
            if priority == "high":
                high.append(item)
            elif priority == "low":
                low.append(item)
            else:
                medium.append(item)
    return {
        "top_insights": high[:10],
        "warnings": medium[:10],
        "opportunities": low[:10],
    }


def aggregate_results(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    consolidated = consolidate_insights(results)
    global_score = calculate_global_intelligence_score(results)
    return {
        "global_intelligence_score": global_score,
        **consolidated,
        "overall_status": "attention" if consolidated["top_insights"] or consolidated["warnings"] else "ok",
        "total_alerts": len(consolidated["top_insights"]) + len(consolidated["warnings"]),
    }


def run_all_agents(context: dict[str, Any] | None = None) -> dict[str, Any]:
    base_context = collect_context(context or {})
    outputs: dict[str, dict[str, Any]] = {}

    # Pipeline coordenado:
    outputs["catalog"] = run_agent("catalog", base_context)
    context_strategy = {**base_context, "agent_outputs": outputs}
    outputs["strategy"] = run_agent("strategy", context_strategy)
    context_risk = {**base_context, "agent_outputs": outputs}
    outputs["risk"] = run_agent("risk", context_risk)
    context_analyst = {**base_context, "agent_outputs": outputs}
    outputs["analyst"] = run_agent("analyst", context_analyst)

    aggregate = aggregate_results(outputs)
    context_explainer = {
        **base_context,
        "agent_outputs": outputs,
        "global_intelligence_score": aggregate["global_intelligence_score"],
        "top_insights": aggregate["top_insights"],
        "warnings": aggregate["warnings"],
        "opportunities": aggregate["opportunities"],
    }
    outputs["explainer"] = run_agent("explainer", context_explainer)

    intelligence_history = None
    run_id = base_context.get("orchestrator_run_id")
    if run_id:
        try:
            with _connect() as conn:
                intelligence_history = build_history_for_current(conn, int(run_id))
        except Exception as exc:
            intelligence_history = {
                "trend": "unknown",
                "summary": f"Histórico inteligente indisponível: {exc}",
                "previous_score": None,
                "current_score": aggregate["global_intelligence_score"].get("score"),
                "score_delta": None,
                "improved_areas": [],
                "worsened_areas": [],
            }

    final = {
        "catalog": outputs["catalog"],
        "strategy": outputs["strategy"],
        "risk": outputs["risk"],
        "analyst": outputs["analyst"],
        "explainer": outputs["explainer"],
        "aggregate": aggregate,
        "global_intelligence_score": aggregate["global_intelligence_score"],
        "top_insights": aggregate["top_insights"],
        "warnings": aggregate["warnings"],
        "opportunities": aggregate["opportunities"],
        "final_explanation": outputs["explainer"].get("final_explanation") or outputs["explainer"].get("summary"),
        "intelligence_history": intelligence_history,
    }
    return final
