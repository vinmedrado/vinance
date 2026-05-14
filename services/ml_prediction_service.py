
from __future__ import annotations

import pickle
from typing import Any

import numpy as np
import pandas as pd

from services.ml_common import bootstrap_ml_tables, connect, json_dump, now_iso, start_ml_run, finish_ml_run
from services.ml_feature_service import latest_feature_frame, build_features
from services.ml_model_registry import get_model


def _history_days_by_ticker(asset_class: str = "all") -> dict[str, int]:
    df, _ = build_features(asset_class=asset_class)
    if df.empty:
        return {}
    hist = df.groupby("ticker")["date"].agg(["min", "max"]).reset_index()
    hist["history_days"] = (hist["max"] - hist["min"]).dt.days
    return {str(r["ticker"]): int(r["history_days"]) for _, r in hist.iterrows()}


def recommendation_label(confidence: float, quality: float) -> str:
    if confidence >= 0.70 and quality >= 65:
        return "Forte"
    if confidence >= 0.55 and quality >= 45:
        return "Boa"
    if quality < 45 or confidence < 0.35:
        return "Evitar"
    return "Neutra"


def explain_prediction(features: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []

    trend = float(features.get("trend_strength") or 0)
    vol = float(features.get("volatility_21d") or 0)
    q = float(features.get("data_quality_score") or 0)
    ret21 = float(features.get("return_21d") or 0)
    dd = float(features.get("drawdown_63d") or 0)
    target_type = prediction.get("target_type")

    if target_type == "regression":
        reasons.append("Modelo prevê retorno esperado.")
    else:
        reasons.append("Modelo prevê probabilidade/classe de retorno futuro.")

    if prediction.get("split_mode") == "temporal":
        reasons.append("Modelo validado em período futuro, mais confiável que split aleatório.")
    if prediction.get("scaler_type") not in (None, "none"):
        reasons.append(f"Features foram padronizadas com scaler {prediction.get('scaler_type')}.")
    if trend > 0:
        reasons.append("Alta tendência recente contribuiu positivamente.")
    if ret21 > 0:
        reasons.append("Retorno de 21 dias positivo reforça o score.")
    if vol > 0.05:
        warnings.append("Volatilidade elevada reduziu a confiança.")
    if dd < -0.15:
        warnings.append("Drawdown recente relevante aumenta o risco.")
    if q < 50:
        warnings.append("Qualidade de dados baixa reduz confiabilidade.")

    rec = prediction.get("recommendation")
    if rec == "Forte":
        reasons.append("Combinação de confiança e qualidade de dados gerou recomendação Forte.")
    elif rec == "Evitar":
        warnings.append("Confiança/qualidade insuficiente gerou recomendação Evitar.")

    return {"reasons": reasons, "warnings": warnings, "summary": " ".join(reasons[:4] + warnings[:2])}


def _ensemble_predict(models_payload, X, target_type: str):
    weights = np.array([float(m[2]) for m in models_payload], dtype=float)
    weights = weights / weights.sum()
    models = [m[1] for m in models_payload]

    if target_type == "regression":
        preds = np.vstack([model.predict(X).astype(float) for model in models])
        return np.average(preds, axis=0, weights=weights), None, None

    classes = list(getattr(models[0], "classes_", []))
    probs = []
    for model in models:
        p = model.predict_proba(X)
        model_classes = list(getattr(model, "classes_", []))
        aligned = np.zeros((len(X), len(classes)))
        for i, cls in enumerate(classes):
            if cls in model_classes:
                aligned[:, i] = p[:, model_classes.index(cls)]
        probs.append(aligned)
    avg_proba = np.average(np.stack(probs), axis=0, weights=weights)
    pred_idx = avg_proba.argmax(axis=1)
    pred = np.array([classes[i] for i in pred_idx])
    return pred, avg_proba, classes


def _heuristic_confidence(row: pd.Series, history_days: int, min_history_days: int) -> float:
    quality = float(row.get("data_quality_score") or 0) / 100
    vol = abs(float(row.get("volatility_21d") or 0))
    hist_factor = min(1.0, history_days / max(1, int(min_history_days)))
    stability = max(0.0, 1.0 - min(vol * 10, 1.0))
    return float(max(0.0, min(1.0, 0.45 * quality + 0.35 * hist_factor + 0.20 * stability)))


def predict(model_id: int, asset_class: str = "all", limit: int = 50, min_quality_score: float = 45, min_history_days: int = 180) -> dict[str, Any]:
    params = {
        "model_id": model_id,
        "asset_class": asset_class,
        "limit": limit,
        "min_quality_score": min_quality_score,
        "min_history_days": min_history_days,
    }
    with connect() as conn:
        bootstrap_ml_tables(conn)
        run_id = start_ml_run(conn, "predict", params)
        try:
            model_row = get_model(model_id)
            if not model_row:
                raise ValueError("Modelo não encontrado.")
            with open(model_row["model_path"], "rb") as f:
                payload = pickle.load(f)

            model = payload["model"]
            features = payload.get("features") or payload.get("selected_features") or payload.get("raw_features")
            if not features:
                raise ValueError("Modelo sem lista de features salva.")
            scaler_obj = payload.get("scaler")
            scaler_type = payload.get("scaler_type", "none")
            target_type = payload.get("target_type") or ("regression" if "regressor" in str(model_row.get("model_type")) else "classification")
            split_mode = "temporal" if '"split_mode": "temporal"' in (model_row.get("metrics_json") or "") else "random"

            latest, warnings = latest_feature_frame(asset_class=asset_class, limit=None)
            if latest.empty:
                raise RuntimeError("Sem ativos com dados suficientes para previsão.")

            hist_days = _history_days_by_ticker(asset_class=asset_class)
            before = len(latest)
            latest["history_days"] = latest["ticker"].astype(str).map(hist_days).fillna(0).astype(int)
            latest = latest[
                (pd.to_numeric(latest.get("data_quality_score", 0), errors="coerce").fillna(0) >= float(min_quality_score))
                & (latest["history_days"] >= int(min_history_days))
            ].copy()
            removed = before - len(latest)
            if latest.empty:
                raise RuntimeError("Nenhum ativo elegível após filtros de qualidade/histórico.")

            for fcol in features:
                if fcol not in latest.columns:
                    latest[fcol] = 0
                latest[fcol] = pd.to_numeric(latest[fcol], errors="coerce").fillna(0)

            X_raw = latest[features].copy()
            if scaler_obj is not None:
                X = pd.DataFrame(scaler_obj.transform(X_raw), columns=features, index=X_raw.index)
            else:
                X = X_raw

            if isinstance(model, list):
                raw_pred, proba, classes = _ensemble_predict(model, X, target_type)
            else:
                raw_pred = model.predict(X)
                proba = None
                classes = list(getattr(model, "classes_", []))
                if target_type == "classification":
                    try:
                        proba = model.predict_proba(X)
                    except Exception:
                        proba = None

            scores = None
            labels = []
            confidences = []

            if target_type == "regression":
                scores = np.asarray(raw_pred, dtype=float)
                labels = ["positive" if s > 0 else "negative" for s in scores]
                confidences = [_heuristic_confidence(row, int(row.get("history_days") or 0), min_history_days) for _, row in latest.iterrows()]
            else:
                if proba is not None:
                    if "high" in classes:
                        idx = classes.index("high")
                        scores = proba[:, idx]
                    elif 1 in classes:
                        idx = classes.index(1)
                        scores = proba[:, idx]
                    elif "1" in classes:
                        idx = classes.index("1")
                        scores = proba[:, idx]
                    else:
                        scores = proba.max(axis=1)
                    confidences = proba.max(axis=1).astype(float).tolist()
                else:
                    scores = np.asarray(raw_pred, dtype=float)
                    confidences = [float(abs(s - 0.5) * 2) for s in scores]
                labels = [str(x) for x in raw_pred]

            pred_date = now_iso()
            ranking_rows = []
            for idx, row in latest.reset_index(drop=True).iterrows():
                score = float(scores[idx])
                confidence = float(confidences[idx])
                quality = float(row.get("data_quality_score") or 0)
                label = str(labels[idx])
                rec = recommendation_label(confidence, quality)
                feature_dict = {f: float(row.get(f) or 0) for f in features}
                feature_dict["data_quality_score"] = quality
                feature_dict["history_days"] = int(row.get("history_days") or 0)
                feature_dict["reliability_status"] = str(row.get("reliability_status") or "unknown")
                explanation = explain_prediction(
                    feature_dict,
                    {
                        "score": score,
                        "label": label,
                        "confidence": confidence,
                        "target_type": target_type,
                        "split_mode": split_mode,
                        "scaler_type": scaler_type,
                        "recommendation": rec,
                    },
                )
                ranking_rows.append({
                    "ticker": str(row.get("ticker")),
                    "prediction_date": pred_date,
                    "predicted_score": score,
                    "predicted_label": label,
                    "confidence": confidence,
                    "data_quality_score": quality,
                    "reliability_status": str(row.get("reliability_status") or "unknown"),
                    "recommendation": rec,
                    "features_json": json_dump(feature_dict),
                    "explanation_json": json_dump(explanation),
                })

            # Ranking estruturado.
            if target_type == "regression":
                ranking_rows = sorted(ranking_rows, key=lambda r: (r["predicted_score"], r["confidence"], r["data_quality_score"]), reverse=True)
            else:
                ranking_rows = sorted(ranking_rows, key=lambda r: (r["confidence"], r["predicted_score"], r["data_quality_score"]), reverse=True)
            ranking_rows = ranking_rows[: int(limit)]

            conn.execute("DELETE FROM ml_predictions WHERE model_id=?", (int(model_id),))
            inserted = 0
            for rank, item in enumerate(ranking_rows, start=1):
                explanation = item["explanation_json"]
                features_json = item["features_json"]
                # Preserva compatibilidade: extras ficam em explanation_json.
                explanation_obj = __import__("json").loads(explanation)
                explanation_obj["rank"] = rank
                explanation_obj["recommendation"] = item["recommendation"]
                conn.execute(
                    """
                    INSERT INTO ml_predictions (
                        model_id, ticker, prediction_date, predicted_score,
                        predicted_label, confidence, features_json, explanation_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(model_id), item["ticker"], item["prediction_date"], item["predicted_score"],
                        item["predicted_label"], item["confidence"], features_json, json_dump(explanation_obj), now_iso(),
                    ),
                )
                inserted += 1
            conn.commit()
            result = {
                "model_id": model_id,
                "target_type": target_type,
                "scaler_type": scaler_type,
                "selected_features": features,
                "predictions": inserted,
                "removed_by_filters": int(removed),
                "min_quality_score": float(min_quality_score),
                "min_history_days": int(min_history_days),
                "warnings": warnings,
            }
            finish_ml_run(conn, run_id, "success", result)
            return result
        except Exception as exc:
            finish_ml_run(conn, run_id, "failed", {}, str(exc))
            raise


def latest_predictions(model_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        bootstrap_ml_tables(conn)
        if model_id:
            rows = conn.execute(
                "SELECT * FROM ml_predictions WHERE model_id=? ORDER BY prediction_date DESC, predicted_score DESC LIMIT ?",
                (int(model_id), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ml_predictions ORDER BY created_at DESC, predicted_score DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]
