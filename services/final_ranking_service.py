
from __future__ import annotations

from typing import Any
import json
import math

from sqlalchemy import text

from services.db_session import db_session

MARKET_ALIASES = {
    "acoes": "equity", "ações": "equity", "acao": "equity", "ação": "equity",
    "equity": "equity", "stock": "equity", "stocks": "equity",
    "fii": "fii", "fiis": "fii", "reit": "fii", "reits": "fii",
    "etf": "etf", "etfs": "etf",
    "bdr": "bdr", "bdrs": "bdr",
    "crypto": "crypto", "cripto": "crypto", "criptos": "crypto",
}

MARKET_LABELS = {
    "equity": "Ações",
    "fii": "FIIs",
    "etf": "ETFs",
    "bdr": "BDRs",
    "crypto": "Cripto",
}

VALID_MARKETS = ["equity", "fii", "etf", "bdr", "crypto"]

DEFAULT_FINAL_RANKING_WEIGHTS = {
    "ml": 0.40,
    "backtest": 0.30,
    "risk": 0.20,
    "quality": 0.10,
}


def normalize_market(market: str | None) -> str:
    raw = str(market or "equity").strip().lower()
    return MARKET_ALIASES.get(raw, raw if raw in VALID_MARKETS else "equity")


def _clean_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _winsorized(values: list[float], lower_q: float = 0.05, upper_q: float = 0.95) -> list[float]:
    clean = sorted([v for v in values if _clean_number(v) is not None])
    if not clean:
        return []
    if len(clean) < 5:
        return clean
    lo_idx = int((len(clean) - 1) * lower_q)
    hi_idx = int((len(clean) - 1) * upper_q)
    lo = clean[lo_idx]
    hi = clean[hi_idx]
    return [max(lo, min(hi, v)) for v in clean]


def normalize_score(value: Any, min_val: float = 0, max_val: float = 1) -> float:
    v = _clean_number(value)
    if v is None:
        return 50.0
    if max_val == min_val:
        return 50.0
    score = ((v - min_val) / (max_val - min_val)) * 100
    return max(0.0, min(100.0, float(score)))


def normalize_by_market(values: list[float | None], method: str = "percentile") -> dict[int, float | None]:
    clean_pairs = [(idx, _clean_number(v)) for idx, v in enumerate(values)]
    clean_pairs = [(idx, v) for idx, v in clean_pairs if v is not None]
    result: dict[int, float | None] = {idx: None for idx in range(len(values))}
    if not clean_pairs:
        return result

    if method == "minmax":
        nums = [v for _, v in clean_pairs]
        wins = _winsorized(nums)
        if not wins:
            return result
        lo, hi = min(wins), max(wins)
        for idx, v in clean_pairs:
            result[idx] = normalize_score(v, lo, hi)
        return result

    ordered = sorted(clean_pairs, key=lambda x: x[1])
    n = len(ordered)
    if n == 1:
        result[ordered[0][0]] = 50.0
        return result
    for rank, (idx, _) in enumerate(ordered):
        result[idx] = round((rank / (n - 1)) * 100, 2)
    return result


def robust_score(value: Any, values: list[float | None], higher_is_better: bool = True) -> float | None:
    v = _clean_number(value)
    clean = [_clean_number(x) for x in values]
    clean = [x for x in clean if x is not None]
    if v is None or not clean:
        return None
    wins = _winsorized(clean)
    if not wins:
        return None
    lo, hi = min(wins), max(wins)
    score = normalize_score(v, lo, hi)
    if not higher_is_better:
        score = 100 - score
    return round(max(0.0, min(100.0, score)), 2)


def normalize_weights(weights: dict[str, float] | None = None) -> dict[str, float]:
    merged = DEFAULT_FINAL_RANKING_WEIGHTS.copy()
    if weights:
        for key in merged:
            if key in weights:
                try:
                    merged[key] = max(0.0, float(weights[key]))
                except Exception:
                    pass
    total = sum(merged.values())
    if total <= 0:
        return DEFAULT_FINAL_RANKING_WEIGHTS.copy()
    return {k: round(v / total, 6) for k, v in merged.items()}


def _json_load(raw: str | None) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_query(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        with db_session() as db:
            rows = db.execute(text(sql), params).mappings().all()
            return [dict(r) for r in rows]
    except Exception:
        return []


def _get_first(data: dict[str, Any] | None, keys: list[str]) -> Any:
    if not data:
        return None
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _raw_ml_metric(prediction: dict[str, Any] | None) -> float | None:
    if not prediction:
        return None
    value = _clean_number(prediction.get("predicted_score"))
    if value is None:
        return None
    label = str(prediction.get("predicted_label") or "").lower()
    if -1 <= value <= 1:
        value = 50 + (value * 100) if value < 0 else value * 100
    if label in {"negative", "low", "0", "false"}:
        value *= 0.75
    return max(0.0, min(100.0, value))


def compute_ml_score(prediction: dict[str, Any] | None) -> float | None:
    metric = _raw_ml_metric(prediction)
    return None if metric is None else round(metric, 2)


def _raw_backtest_metrics(backtest_data: dict[str, Any] | None) -> dict[str, float | None]:
    if not backtest_data:
        return {"return": None, "winrate": None, "drawdown": None, "trade_count": None, "consistency": None}

    roi = _clean_number(_get_first(backtest_data, ["roi", "ROI", "return", "total_return", "profit_pct"]))
    winrate = _clean_number(_get_first(backtest_data, ["winrate", "win_rate", "accuracy", "hit_rate"]))
    drawdown = _clean_number(_get_first(backtest_data, ["drawdown", "max_drawdown", "mdd"]))
    trade_count = _clean_number(_get_first(backtest_data, ["total_trades", "trades", "n_trades", "trade_count"]))
    consistency = _clean_number(_get_first(backtest_data, ["consistency", "consistency_score", "profit_factor", "sharpe"]))

    if roi is not None and -1 <= roi <= 1:
        roi *= 100
    if winrate is not None and 0 <= winrate <= 1:
        winrate *= 100
    if drawdown is not None and 0 <= abs(drawdown) <= 1:
        drawdown *= 100
    if drawdown is not None:
        drawdown = abs(drawdown)

    return {"return": roi, "winrate": winrate, "drawdown": drawdown, "trade_count": trade_count, "consistency": consistency}


def compute_backtest_score(backtest_data: dict[str, Any] | None, market_context: dict[str, list[float | None]] | None = None) -> tuple[float | None, list[str]]:
    warnings: list[str] = []
    metrics = _raw_backtest_metrics(backtest_data)
    if all(v is None for v in metrics.values()):
        return None, ["missing_backtest"]

    context = market_context or {}
    return_score = robust_score(metrics["return"], context.get("return", []), True)
    winrate_score = robust_score(metrics["winrate"], context.get("winrate", []), True)
    drawdown_score = robust_score(metrics["drawdown"], context.get("drawdown", []), False)
    trade_count_score = robust_score(metrics["trade_count"], context.get("trade_count", []), True)
    consistency_score = robust_score(metrics["consistency"], context.get("consistency", []), True)

    trade_count = metrics["trade_count"]
    if trade_count is not None and trade_count < 10:
        warnings.append("low_trade_count")
    if metrics["drawdown"] is not None and metrics["drawdown"] >= 25:
        warnings.append("high_drawdown")

    score = (
        ((return_score if return_score is not None else 50) * 0.40)
        + ((winrate_score if winrate_score is not None else 50) * 0.20)
        + ((drawdown_score if drawdown_score is not None else 50) * 0.20)
        + ((trade_count_score if trade_count_score is not None else 50) * 0.10)
        + ((consistency_score if consistency_score is not None else 50) * 0.10)
    )

    if trade_count is not None and trade_count < 10:
        score *= 0.70

    return round(max(0.0, min(100.0, score)), 2), warnings


def _raw_risk_metrics(asset_data: dict[str, Any]) -> dict[str, float | None]:
    volatility = _clean_number(_get_first(asset_data, ["volatility", "volatility_21d", "volatility_63d"]))
    drawdown = _clean_number(_get_first(asset_data, ["drawdown", "drawdown_63d", "max_drawdown"]))
    stability = _clean_number(_get_first(asset_data, ["stability", "stability_score", "consistency", "trend_strength"]))

    if volatility is not None and 0 <= abs(volatility) <= 1:
        volatility *= 100
    if drawdown is not None and 0 <= abs(drawdown) <= 1:
        drawdown *= 100
    if drawdown is not None:
        drawdown = abs(drawdown)
    if stability is not None and -1 <= stability <= 1:
        stability = 50 + (stability * 50)

    return {"volatility": volatility, "drawdown": drawdown, "stability": stability}


def compute_risk_score(asset_data: dict[str, Any], market_context: dict[str, list[float | None]] | None = None) -> tuple[float | None, list[str]]:
    warnings: list[str] = []
    metrics = _raw_risk_metrics(asset_data)
    if metrics["volatility"] is None and metrics["drawdown"] is None and metrics["stability"] is None:
        return None, ["missing_risk"]

    context = market_context or {}
    drawdown_score = robust_score(metrics["drawdown"], context.get("drawdown", []), False)
    volatility_score = robust_score(metrics["volatility"], context.get("volatility", []), False)
    stability_score = robust_score(metrics["stability"], context.get("stability", []), True)

    if metrics["drawdown"] is not None and metrics["drawdown"] >= 25:
        warnings.append("high_drawdown")

    score = (
        ((drawdown_score if drawdown_score is not None else 50) * 0.45)
        + ((volatility_score if volatility_score is not None else 50) * 0.35)
        + ((stability_score if stability_score is not None else 50) * 0.20)
    )
    return round(max(0.0, min(100.0, score)), 2), warnings


def compute_data_completeness_score(ml_score, backtest_score, risk_score, data_quality_score) -> float:
    present = sum(x is not None for x in [ml_score, backtest_score, risk_score, data_quality_score])
    return round((present / 4) * 100, 2)


def compute_final_score(asset: dict[str, Any], weights: dict[str, float] | None = None) -> float:
    used_weights = normalize_weights(weights)
    component_values = {
        "ml": asset.get("ml_score"),
        "backtest": asset.get("backtest_score"),
        "risk": asset.get("risk_score"),
        "quality": asset.get("data_quality_score"),
    }

    present_weights = {k: used_weights[k] for k, v in component_values.items() if v is not None}
    total_weight = sum(present_weights.values())
    if total_weight <= 0:
        return 0.0

    score = 0.0
    for key, value in component_values.items():
        if value is not None:
            score += float(value) * (used_weights[key] / total_weight)

    return round(max(0.0, min(100.0, score)), 2)


def classify_final(score_final: float, data_completeness_score: float, eligible: bool) -> str:
    if not eligible:
        return "Evitar"
    if data_completeness_score < 75:
        return "Neutra" if score_final >= 45 else "Evitar"
    if score_final >= 75:
        return "Forte"
    if score_final >= 60:
        return "Boa"
    if score_final >= 45:
        return "Neutra"
    return "Evitar"


def build_final_explanation(asset: dict[str, Any]) -> str:
    warnings = set(asset.get("warnings") or [])
    parts: list[str] = []

    if asset.get("ml_score") is not None:
        parts.append("previsão positiva" if asset["ml_score"] >= 65 else "previsão fraca" if asset["ml_score"] < 45 else "previsão equilibrada")
    if asset.get("backtest_score") is not None:
        parts.append("bom desempenho histórico" if asset["backtest_score"] >= 65 else "histórico pouco favorável" if asset["backtest_score"] < 45 else "histórico equilibrado")
    if asset.get("risk_score") is not None:
        parts.append("risco controlado" if asset["risk_score"] >= 65 else "risco elevado" if asset["risk_score"] < 45 else "risco moderado")
    if asset.get("data_quality_score") is not None:
        parts.append("dados confiáveis" if asset["data_quality_score"] >= 65 else "qualidade de dados baixa" if asset["data_quality_score"] < 45 else "qualidade de dados aceitável")

    if "low_trade_count" in warnings:
        parts.append("amostra histórica pequena")
    if asset.get("data_completeness_score", 0) < 75:
        parts.append("dados ainda incompletos")

    if not parts:
        return "Este ativo possui leitura equilibrada, sem vantagem clara no momento."

    if asset.get("classification") in {"Forte", "Boa"}:
        return "Este ativo aparece no ranking por apresentar " + ", ".join(parts) + "."
    if asset.get("classification") == "Neutra":
        return "Este ativo aparece como acompanhamento por ter " + ", ".join(parts) + "."
    return "Este ativo exige cautela por apresentar " + ", ".join(parts) + "."


def _load_catalog(tenant_id: str | None, market: str) -> list[dict[str, Any]]:
    market = normalize_market(market)
    aliases = {
        "equity": ["equity", "stock", "acao", "ações", "acoes"],
        "fii": ["fii", "fiis", "reit", "reits"],
        "etf": ["etf", "etfs"],
        "bdr": ["bdr", "bdrs"],
        "crypto": ["crypto", "cripto", "criptos"],
    }.get(market, [market])

    rows = []
    for alias in aliases:
        rows.extend(_safe_query(
            """
            SELECT
                ticker,
                COALESCE(name, asset_name, ticker) AS name,
                COALESCE(asset_class, 'equity') AS asset_class,
                COALESCE(data_quality_score, quality_score, score_quality, quality, 50) AS data_quality_score,
                COALESCE(reliability_status, status, validation_status, 'unknown') AS reliability_status
            FROM asset_catalog
            WHERE LOWER(COALESCE(asset_class, 'equity')) = :alias
              AND (:tenant_id IS NULL OR tenant_id = :tenant_id)
            """,
            {"alias": alias, "tenant_id": tenant_id},
        ))

    seen = set()
    unique = []
    for row in rows:
        ticker = str(row.get("ticker"))
        if ticker not in seen:
            unique.append(row)
            seen.add(ticker)
    return unique


def _load_latest_predictions(tenant_id: str | None) -> dict[str, dict[str, Any]]:
    rows = _safe_query(
        """
        SELECT DISTINCT ON (ticker)
            ticker, model_id, prediction_date, predicted_score, predicted_label,
            confidence, features_json, explanation_json
        FROM ml_predictions
        WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
        ORDER BY ticker, prediction_date DESC, id DESC
        """,
        {"tenant_id": tenant_id},
    )
    return {str(r["ticker"]): r for r in rows}


def _load_backtest_data(tenant_id: str | None) -> dict[str, dict[str, Any]]:
    candidates = ["backtest_metrics", "backtest_results", "backtest_runs", "strategy_backtest_results"]
    out: dict[str, dict[str, Any]] = {}
    for table_name in candidates:
        rows = _safe_query(
            f"""
            SELECT *
            FROM {table_name}
            WHERE (:tenant_id IS NULL OR tenant_id = :tenant_id)
            ORDER BY id DESC
            LIMIT 5000
            """,
            {"tenant_id": tenant_id},
        )
        for row in rows:
            ticker = row.get("ticker") or row.get("asset") or row.get("symbol") or row.get("asset_symbol")
            if ticker and str(ticker) not in out:
                out[str(ticker)] = row
    return out


def _features_from_prediction(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {}
    data = _json_load(prediction.get("features_json"))
    return data if isinstance(data, dict) else {}


def _build_contexts(catalog_rows: list[dict[str, Any]], predictions: dict[str, dict[str, Any]], backtests: dict[str, dict[str, Any]]) -> dict[str, dict[str, list[float | None]]]:
    ml_values = []
    backtest_context = {"return": [], "winrate": [], "drawdown": [], "trade_count": [], "consistency": []}
    risk_context = {"volatility": [], "drawdown": [], "stability": []}
    quality_values = []

    for catalog in catalog_rows:
        ticker = str(catalog.get("ticker"))
        pred = predictions.get(ticker)
        bt = backtests.get(ticker)
        features = _features_from_prediction(pred)
        ml_values.append(_raw_ml_metric(pred))
        bt_metrics = _raw_backtest_metrics(bt)
        for k in backtest_context:
            backtest_context[k].append(bt_metrics.get(k))
        risk_metrics = _raw_risk_metrics({**features, **catalog})
        for k in risk_context:
            risk_context[k].append(risk_metrics.get(k))
        quality_values.append(_clean_number(catalog.get("data_quality_score")))

    return {"ml": {"ml": ml_values}, "backtest": backtest_context, "risk": risk_context, "quality": {"quality": quality_values}}


def compute_ranked_asset(catalog, prediction, backtest, contexts=None, weights=None) -> dict[str, Any]:
    contexts = contexts or {}
    features = _features_from_prediction(prediction)
    warnings: list[str] = []

    raw_ml = _raw_ml_metric(prediction)
    ml_score = robust_score(raw_ml, contexts.get("ml", {}).get("ml", []), True) if raw_ml is not None else None
    if ml_score is None:
        warnings.append("missing_ml")

    backtest_score, bt_warnings = compute_backtest_score(backtest, contexts.get("backtest", {}))
    warnings.extend(bt_warnings)

    risk_payload = {**features, **catalog, "confidence": (prediction or {}).get("confidence", 0.5)}
    risk_score, risk_warnings = compute_risk_score(risk_payload, contexts.get("risk", {}))
    warnings.extend(risk_warnings)

    dq_raw = _clean_number(catalog.get("data_quality_score"))
    data_quality_score = robust_score(dq_raw, contexts.get("quality", {}).get("quality", []), True) if dq_raw is not None else None
    if data_quality_score is None:
        warnings.append("missing_quality")
    elif dq_raw is not None and dq_raw < 45:
        warnings.append("low_quality_data")

    data_completeness_score = compute_data_completeness_score(ml_score, backtest_score, risk_score, data_quality_score)
    eligible = not ((dq_raw is not None and dq_raw < 45) or data_completeness_score < 50)

    used_weights = normalize_weights(weights)
    asset = {
        "ticker": catalog.get("ticker"),
        "name": catalog.get("name") or catalog.get("ticker"),
        "asset_class": normalize_market(catalog.get("asset_class")),
        "market_label": MARKET_LABELS.get(normalize_market(catalog.get("asset_class")), "Ações"),
        "ml_score": ml_score,
        "backtest_score": backtest_score,
        "risk_score": risk_score,
        "data_quality_score": data_quality_score,
        "raw_data_quality_score": dq_raw,
        "data_completeness_score": data_completeness_score,
        "confidence": float((prediction or {}).get("confidence") or 0),
        "model_id": (prediction or {}).get("model_id"),
        "prediction_date": (prediction or {}).get("prediction_date"),
        "reliability_status": catalog.get("reliability_status", "unknown"),
        "eligible": eligible,
        "warnings": sorted(set(warnings)),
        "weights_used": used_weights,
    }
    asset["score_final"] = compute_final_score(asset, used_weights)
    asset["classification"] = classify_final(asset["score_final"], data_completeness_score, eligible)
    asset["score_breakdown"] = {
        "ml_score": asset["ml_score"],
        "backtest_score": asset["backtest_score"],
        "risk_score": asset["risk_score"],
        "data_quality_score": asset["data_quality_score"],
        "data_completeness_score": asset["data_completeness_score"],
        "weights": used_weights,
    }
    asset["explanation"] = build_final_explanation(asset)
    return asset


def get_ranked_assets_by_market(market: str, limit: int = 50, tenant_id: str | None = None, weights: dict[str, float] | None = None, include_ineligible: bool = False, normalization_method: str = "percentile") -> list[dict[str, Any]]:
    market = normalize_market(market)
    used_weights = normalize_weights(weights)
    catalog_rows = _load_catalog(tenant_id, market)
    predictions = _load_latest_predictions(tenant_id)
    backtests = _load_backtest_data(tenant_id)
    contexts = _build_contexts(catalog_rows, predictions, backtests)

    assets = []
    for catalog in catalog_rows:
        ticker = str(catalog.get("ticker"))
        asset = compute_ranked_asset(catalog, predictions.get(ticker), backtests.get(ticker), contexts, used_weights)
        if include_ineligible or asset.get("eligible"):
            assets.append(asset)

    assets.sort(key=lambda x: x.get("score_final", 0), reverse=True)
    return assets[: int(limit)]


def get_best_assets_by_all_markets(limit_per_market: int = 10, tenant_id: str | None = None, weights: dict[str, float] | None = None) -> dict[str, list[dict[str, Any]]]:
    return {market: get_ranked_assets_by_market(market, limit=limit_per_market, tenant_id=tenant_id, weights=weights) for market in VALID_MARKETS}


def get_market_leader(market: str, tenant_id: str | None = None, weights: dict[str, float] | None = None) -> dict[str, Any] | None:
    ranked = get_ranked_assets_by_market(market, limit=1, tenant_id=tenant_id, weights=weights)
    return ranked[0] if ranked else None
