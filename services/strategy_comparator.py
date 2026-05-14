from __future__ import annotations

import json
from db import pg_compat as dbcompat
from typing import Any, Dict, List, Optional

from services.strategy_interpreter import calculate_strategy_score


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _parse_json(value: Any) -> Dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dbcompat.Row):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _safe_table_exists(conn: dbcompat.Connection, table: str) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table,),
        ).fetchone()
        return row is not None
    except Exception:
        return False


def _final_value(row: Dict[str, Any]) -> Optional[float]:
    data = _parse_json(row.get("metrics_json"))
    for key in ["final_value", "final_equity", "equity_final"]:
        if key in data:
            try:
                return float(data[key])
            except Exception:
                pass
    try:
        return _num(row.get("initial_capital"), 0.0) * (1.0 + _num(row.get("total_return"), 0.0))
    except Exception:
        return None


def load_backtest_metrics(conn: dbcompat.Connection) -> List[Dict[str, Any]]:
    """Carrega backtests e métricas em formato comum para comparação visual.

    Não altera o banco. Retorna lista vazia se as tabelas ainda não existirem.
    """
    if not _safe_table_exists(conn, "backtest_runs") or not _safe_table_exists(conn, "backtest_metrics"):
        return []

    conn.row_factory = dbcompat.Row
    rows = conn.execute(
        """
        SELECT
            br.id,
            br.strategy_name AS strategy,
            br.asset_class,
            br.start_date,
            br.end_date,
            br.top_n,
            br.rebalance_frequency,
            br.status,
            br.created_at,
            br.finished_at,
            br.initial_capital,
            br.params_json,
            bm.total_return,
            bm.annual_return,
            bm.max_drawdown,
            bm.sharpe_ratio,
            bm.win_rate,
            bm.total_trades,
            bm.turnover,
            bm.metrics_json
        FROM backtest_runs br
        LEFT JOIN backtest_metrics bm ON bm.backtest_id = br.id
        ORDER BY br.id DESC
        """
    ).fetchall()

    result: List[Dict[str, Any]] = []
    for raw in rows:
        row = _row_to_dict(raw)
        row["final_value"] = _final_value(row)
        row["strategy_ui_score"] = calculate_strategy_score(row)
        row["comparison_score"] = calculate_comparison_score(row)
        result.append(row)
    return result


def calculate_comparison_score(item: Dict[str, Any]) -> int:
    """Score composto 0-100: retorno 30%, Sharpe 25%, drawdown 25%, turnover 20%.

    Usa normalizações conservadoras, próprias para interface, sem persistência.
    """
    total_return = _num(item.get("total_return"))
    sharpe = _num(item.get("sharpe_ratio"))
    drawdown = _num(item.get("max_drawdown"))
    turnover = _num(item.get("turnover"))

    return_points = max(0.0, min(30.0, (total_return / 0.30) * 30.0))
    sharpe_points = max(0.0, min(25.0, (sharpe / 1.0) * 25.0))

    if drawdown >= -0.10:
        dd_points = 25.0
    elif drawdown >= -0.20:
        dd_points = 20.0
    elif drawdown >= -0.30:
        dd_points = 14.0
    elif drawdown >= -0.40:
        dd_points = 7.0
    else:
        dd_points = 0.0

    if turnover <= 3:
        turnover_points = 20.0
    elif turnover <= 10:
        turnover_points = 16.0
    elif turnover <= 15:
        turnover_points = 12.0
    elif turnover <= 25:
        turnover_points = 7.0
    elif turnover <= 40:
        turnover_points = 3.0
    else:
        turnover_points = 0.0

    score = return_points + sharpe_points + dd_points + turnover_points
    return int(max(0, min(100, round(score))))


def rank_backtests(backtests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = []
    for item in backtests:
        enriched = dict(item)
        enriched["comparison_score"] = int(enriched.get("comparison_score") or calculate_comparison_score(enriched))
        ranked.append(enriched)
    ranked.sort(
        key=lambda x: (
            _num(x.get("comparison_score")),
            _num(x.get("total_return")),
            _num(x.get("sharpe_ratio")),
            _num(x.get("max_drawdown")),
            -_num(x.get("turnover")),
        ),
        reverse=True,
    )
    for idx, item in enumerate(ranked, start=1):
        item["rank_position"] = idx
    return ranked


def get_top_strategies(backtests: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    return rank_backtests(backtests)[: max(0, int(limit))]


def _average(backtests: List[Dict[str, Any]], key: str) -> float:
    values = [_num(x.get(key)) for x in backtests if x.get(key) is not None]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _find_current(current: Dict[str, Any], ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
    current_id = current.get("id") or current.get("backtest_id")
    if current_id is not None:
        for item in ranked:
            if str(item.get("id")) == str(current_id):
                return item
    enriched = dict(current)
    enriched["comparison_score"] = calculate_comparison_score(enriched)
    return enriched


def compare_to_best(current: Dict[str, Any], all_backtests: List[Dict[str, Any]]) -> Dict[str, Any]:
    ranked = rank_backtests(all_backtests)
    if not ranked:
        return {"has_comparison": False, "message": "Ainda não há histórico suficiente para comparar."}

    current_ranked = _find_current(current, ranked)
    position = int(current_ranked.get("rank_position") or 0)
    best = ranked[0]
    best_return = max(all_backtests, key=lambda x: _num(x.get("total_return")))
    best_sharpe = max(all_backtests, key=lambda x: _num(x.get("sharpe_ratio")))

    return {
        "has_comparison": True,
        "position": position,
        "total": len(ranked),
        "best_overall": best,
        "best_return": best_return,
        "best_sharpe": best_sharpe,
        "diff_to_best_return": _num(current_ranked.get("total_return")) - _num(best_return.get("total_return")),
        "diff_to_best_sharpe": _num(current_ranked.get("sharpe_ratio")) - _num(best_sharpe.get("sharpe_ratio")),
        "diff_to_best_score": _num(current_ranked.get("comparison_score")) - _num(best.get("comparison_score")),
    }


def compare_to_average(current: Dict[str, Any], all_backtests: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not all_backtests:
        return {"has_comparison": False, "message": "Ainda não há backtests para média."}

    avg_return = _average(all_backtests, "total_return")
    avg_sharpe = _average(all_backtests, "sharpe_ratio")
    avg_drawdown = _average(all_backtests, "max_drawdown")
    avg_turnover = _average(all_backtests, "turnover")
    avg_score = _average(all_backtests, "comparison_score")

    current_score = calculate_comparison_score(current)
    return {
        "has_comparison": True,
        "avg_return": avg_return,
        "avg_sharpe": avg_sharpe,
        "avg_drawdown": avg_drawdown,
        "avg_turnover": avg_turnover,
        "avg_score": avg_score,
        "above_avg_return": _num(current.get("total_return")) >= avg_return,
        "above_avg_sharpe": _num(current.get("sharpe_ratio")) >= avg_sharpe,
        "turnover_above_avg": _num(current.get("turnover")) > avg_turnover,
        "drawdown_worse_avg": _num(current.get("max_drawdown")) < avg_drawdown,
        "score_above_avg": current_score >= avg_score,
        "diff_return_avg": _num(current.get("total_return")) - avg_return,
        "diff_sharpe_avg": _num(current.get("sharpe_ratio")) - avg_sharpe,
        "diff_turnover_avg": _num(current.get("turnover")) - avg_turnover,
        "diff_drawdown_avg": _num(current.get("max_drawdown")) - avg_drawdown,
        "diff_score_avg": current_score - avg_score,
    }


def summarize_comparison(current: Dict[str, Any], all_backtests: List[Dict[str, Any]]) -> str:
    best = compare_to_best(current, all_backtests)
    avg = compare_to_average(current, all_backtests)
    if not best.get("has_comparison") or not avg.get("has_comparison"):
        return "Ainda não há histórico suficiente para uma comparação robusta. Rode mais backtests para criar uma base de comparação."

    position = best.get("position") or "-"
    total = best.get("total") or "-"
    ret = _num(current.get("total_return"))
    dd_worse = avg.get("drawdown_worse_avg")
    turn_above = avg.get("turnover_above_avg")
    score_above = avg.get("score_above_avg")

    if score_above and not dd_worse and not turn_above:
        return f"Essa estratégia está na posição {position}/{total} e está acima da média com risco e rotação controlados."
    if ret > 0 and dd_worse:
        return f"Essa estratégia está na posição {position}/{total}. Ela é lucrativa, mas possui drawdown pior que a média."
    if ret > 0 and turn_above:
        return f"Essa estratégia está na posição {position}/{total}. Ela gera retorno, porém com turnover acima da média."
    if score_above:
        return f"Essa estratégia está na posição {position}/{total} e supera a média geral dos backtests."
    return f"Essa estratégia está na posição {position}/{total} e ainda fica abaixo da média geral. Vale testar outro período ou ajuste de parâmetros."


def compare_to_benchmarks(current: Dict[str, Any], benchmark: Dict[str, Any]) -> Dict[str, Any]:
    """Compara uma estratégia com IBOV e CDI para uso visual na interface."""
    strategy_return = _num(current.get("total_return"))
    ibov_return = _num(benchmark.get("ibov_return"))
    cdi_return = _num(benchmark.get("cdi_return"))
    return {
        "diff_to_ibov": strategy_return - ibov_return,
        "diff_to_cdi": strategy_return - cdi_return,
        "above_ibov": strategy_return >= ibov_return,
        "above_cdi": strategy_return >= cdi_return,
    }
