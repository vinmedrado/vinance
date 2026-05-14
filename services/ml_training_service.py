
from __future__ import annotations

from typing import Any
import os
import pickle
import numpy as np
import pandas as pd

from services.ml_common import (
    MODELS_DIR, bootstrap_ml_tables, connect, json_dump, now_iso,
    start_ml_run, finish_ml_run
)
from services.ml_dataset_service import FEATURE_COLUMNS, get_dataset, load_dataset_dataframe


CLASSIFICATION_TARGETS = {"future_return_positive", "future_return_class"}
REGRESSION_TARGETS = {"future_return_regression"}


def _target_type(target: str) -> str:
    return "regression" if target in REGRESSION_TARGETS else "classification"


def _temporal_split(df: pd.DataFrame, test_size: float):
    ordered = df.sort_values("date").reset_index(drop=True)
    split_idx = max(1, int(len(ordered) * (1 - float(test_size))))
    split_idx = min(split_idx, len(ordered) - 1)
    return ordered.iloc[:split_idx].copy(), ordered.iloc[split_idx:].copy()


def _random_split(df: pd.DataFrame, y, test_size: float, random_state: int):
    from sklearn.model_selection import train_test_split
    stratify = y if getattr(y, "nunique", lambda: 0)() > 1 and len(y) >= 10 else None
    train_idx, test_idx = train_test_split(
        df.index,
        test_size=float(test_size),
        random_state=int(random_state),
        stratify=stratify,
    )
    return df.loc[train_idx].copy(), df.loc[test_idx].copy()


def _classification_metrics(y_test, pred, proba=None) -> dict[str, Any]:
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
    metrics = {
        "accuracy": float(accuracy_score(y_test, pred)),
        "precision": float(precision_score(y_test, pred, average="weighted", zero_division=0)),
        "recall": float(recall_score(y_test, pred, average="weighted", zero_division=0)),
        "f1": float(f1_score(y_test, pred, average="weighted", zero_division=0)),
    }
    if proba is not None:
        try:
            if len(set(y_test)) == 2:
                metrics["roc_auc"] = float(roc_auc_score(y_test, proba[:, 1] if getattr(proba, "ndim", 1) > 1 else proba))
            else:
                metrics["roc_auc"] = float(roc_auc_score(y_test, proba, multi_class="ovr", average="weighted"))
        except Exception:
            metrics["roc_auc"] = None
    return metrics


def _regression_metrics(y_test, pred) -> dict[str, Any]:
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y_test = pd.to_numeric(y_test, errors="coerce")
    pred = np.asarray(pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    directional = float((np.sign(pred) == np.sign(y_test)).mean()) if len(y_test) else None
    return {
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": rmse,
        "r2": float(r2_score(y_test, pred)) if len(y_test) > 1 else None,
        "directional_accuracy": directional,
    }


def _build_scaler(scaler: str):
    if scaler == "standard":
        from sklearn.preprocessing import StandardScaler
        return StandardScaler()
    if scaler == "minmax":
        from sklearn.preprocessing import MinMaxScaler
        return MinMaxScaler()
    return None


def _make_model(model_type: str, target_kind: str, random_state: int):
    if model_type == "xgboost":
        if target_kind == "regression":
            from xgboost import XGBRegressor
            return XGBRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=6,
                subsample=0.8, colsample_bytree=0.8,
                random_state=int(random_state), eval_metric="rmse", verbosity=0,
            ), "xgboost_regressor"
        from xgboost import XGBClassifier
        return XGBClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8,
            random_state=int(random_state), eval_metric="logloss",
            verbosity=0, use_label_encoder=False,
        ), "xgboost_classifier"

    if model_type == "lightgbm":
        if target_kind == "regression":
            from lightgbm import LGBMRegressor
            return LGBMRegressor(
                n_estimators=300, learning_rate=0.05, max_depth=6,
                subsample=0.8, colsample_bytree=0.8,
                random_state=int(random_state), verbose=-1,
            ), "lightgbm_regressor"
        from lightgbm import LGBMClassifier
        return LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6,
            subsample=0.8, colsample_bytree=0.8,
            random_state=int(random_state), verbose=-1,
        ), "lightgbm_classifier"

    if model_type == "ensemble_basic":
        if target_kind == "regression":
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            return [
                ("random_forest_regressor", RandomForestRegressor(n_estimators=200, random_state=int(random_state)), 0.5),
                ("gradient_boosting_regressor", GradientBoostingRegressor(random_state=int(random_state)), 0.5),
            ], "ensemble_basic_regressor"
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        return [
            ("random_forest_classifier", RandomForestClassifier(n_estimators=200, random_state=int(random_state), class_weight="balanced"), 0.5),
            ("gradient_boosting_classifier", GradientBoostingClassifier(random_state=int(random_state)), 0.5),
        ], "ensemble_basic_classifier"

    if target_kind == "regression":
        if model_type in {"gradient_boosting", "gb"}:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(random_state=int(random_state)), "gradient_boosting_regressor"
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(n_estimators=200, random_state=int(random_state)), "random_forest_regressor"

    if model_type in {"gradient_boosting", "gb"}:
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier(random_state=int(random_state)), "gradient_boosting_classifier"
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(n_estimators=200, random_state=int(random_state), class_weight="balanced"), "random_forest_classifier"


def _leakage_checks(data: pd.DataFrame, train_df: pd.DataFrame, test_df: pd.DataFrame, target: str, split_mode: str) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    passed = True

    if "date" not in data.columns or data["date"].isna().any():
        warnings.append("Há datas ausentes no dataset.")
        passed = False

    unique_dates = data["date"].nunique()
    if unique_dates < 20:
        warnings.append(f"Dataset possui poucas datas únicas: {unique_dates}.")

    if not data.sort_values(["ticker", "date"]).index.equals(data.index):
        warnings.append("Dataset não estava ordenado por ticker/date; treino ordenou internamente.")

    null_rate = float(data[target].isna().mean()) if target in data.columns else 1.0
    if null_rate > 0.2:
        warnings.append(f"Target possui muitos nulos: {null_rate:.1%}.")
        passed = False

    if split_mode == "temporal":
        train_end = train_df["date"].max()
        test_start = test_df["date"].min()
        if pd.isna(train_end) or pd.isna(test_start) or not (train_end < test_start):
            warnings.append("Split temporal inválido: train_end não é menor que test_start.")
            passed = False

    forbidden = [c for c in data.columns if c.startswith("future_") and c != target]
    if forbidden:
        warnings.append(f"Colunas futuras removidas das features para evitar leakage: {forbidden}")

    return passed, warnings


def _select_by_correlation(X_train: pd.DataFrame, threshold: float) -> tuple[list[str], list[str]]:
    corr = X_train.corr(numeric_only=True).abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    removed = [column for column in upper.columns if any(upper[column] > float(threshold))]
    selected = [c for c in X_train.columns if c not in removed]
    return selected, removed


def _select_by_importance(X_train, y_train, features: list[str], target_kind: str, random_state: int, top_features: int) -> tuple[list[str], list[str], dict[str, float]]:
    base_model, _ = _make_model("random_forest", target_kind, random_state)
    base_model.fit(X_train[features], y_train)
    importance = {}
    if hasattr(base_model, "feature_importances_"):
        importance = {f: float(v) for f, v in zip(features, base_model.feature_importances_)}
    ordered = [f for f, _ in sorted(importance.items(), key=lambda kv: kv[1], reverse=True)]
    selected = ordered[: max(1, min(int(top_features), len(ordered)))] if ordered else features[: max(1, min(int(top_features), len(features)))]
    removed = [f for f in features if f not in selected]
    return selected, removed, importance


def _ensemble_predict(models_payload, X, target_kind: str):
    names = [m[0] for m in models_payload]
    models = [m[1] for m in models_payload]
    weights = np.array([float(m[2]) for m in models_payload], dtype=float)
    weights = weights / weights.sum()

    if target_kind == "regression":
        preds = np.vstack([model.predict(X).astype(float) for model in models])
        return np.average(preds, axis=0, weights=weights), None

    # Classificação: tenta média de probabilidades alinhadas pelas classes do primeiro modelo.
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
    return pred, avg_proba


def train_model(
    dataset_id: int,
    model_type: str = "random_forest",
    test_size: float = 0.2,
    random_state: int = 42,
    split_mode: str = "temporal",
    scaler: str = "standard",
    feature_selection: str = "none",
    top_features: int = 20,
    correlation_threshold: float = 0.95,
) -> dict[str, Any]:
    if split_mode not in {"temporal", "random"}:
        raise ValueError("split_mode deve ser temporal ou random.")
    if scaler not in {"none", "standard", "minmax"}:
        raise ValueError("scaler deve ser none, standard ou minmax.")
    if feature_selection not in {"none", "importance", "correlation"}:
        raise ValueError("feature_selection deve ser none, importance ou correlation.")
    if model_type not in {"random_forest", "gradient_boosting", "gb", "ensemble_basic", "xgboost", "lightgbm"}:
        raise ValueError("model_type inválido.")

    params = {
        "dataset_id": dataset_id,
        "model_type": model_type,
        "test_size": test_size,
        "random_state": random_state,
        "split_mode": split_mode,
        "scaler": scaler,
        "feature_selection": feature_selection,
        "top_features": top_features,
        "correlation_threshold": correlation_threshold,
    }

    with connect() as conn:
        bootstrap_ml_tables(conn)
        run_id = start_ml_run(conn, "train_model", params)
        try:
            ds = get_dataset(dataset_id)
            if not ds:
                raise ValueError("Dataset não encontrado.")
            df = load_dataset_dataframe(dataset_id)
            target = ds.get("target_name") or "future_return_positive"
            target_kind = _target_type(target)
            if target not in df.columns:
                raise ValueError(f"Target {target} não existe no dataset.")

            raw_features = [c for c in FEATURE_COLUMNS if c in df.columns]
            if not raw_features:
                raise ValueError("Nenhuma feature numérica encontrada.")

            data = df.dropna(subset=[target]).copy()
            if "date" not in data.columns:
                raise ValueError("Dataset sem coluna date; split temporal não é possível.")
            data["date"] = pd.to_datetime(data["date"], errors="coerce")
            data = data.dropna(subset=["date"]).sort_values(["ticker", "date"]).reset_index(drop=True)

            # Garante que colunas futuras nunca entram como features.
            features = [f for f in raw_features if not f.startswith("future_")]
            for f in features:
                data[f] = pd.to_numeric(data[f], errors="coerce").fillna(0)

            if target_kind == "regression":
                data["_y"] = pd.to_numeric(data[target], errors="coerce")
                data = data.dropna(subset=["_y"])
            else:
                data["_y"] = data[target].astype(str if target == "future_return_class" else int)

            if len(data) < 20:
                raise ValueError("Dataset pequeno demais para treino mínimo.")
            if target_kind == "classification" and data["_y"].nunique() < 2:
                raise ValueError("Target possui apenas uma classe. Treino classificador não é válido.")

            if split_mode == "temporal":
                train_df, test_df = _temporal_split(data, test_size)
            else:
                train_df, test_df = _random_split(data, data["_y"], test_size, random_state)

            leakage_passed, leakage_warnings = _leakage_checks(data, train_df, test_df, target, split_mode)

            X_train_raw = train_df[features].copy()
            X_test_raw = test_df[features].copy()
            y_train = train_df["_y"]
            y_test = test_df["_y"]

            removed_features: list[str] = []
            selection_importance: dict[str, float] = {}
            selected_features = list(features)

            if feature_selection == "correlation":
                selected_features, removed_features = _select_by_correlation(X_train_raw, correlation_threshold)
            elif feature_selection == "importance":
                selected_features, removed_features, selection_importance = _select_by_importance(
                    X_train_raw, y_train, features, target_kind, random_state, top_features
                )

            X_train_raw = X_train_raw[selected_features]
            X_test_raw = X_test_raw[selected_features]

            scaler_obj = _build_scaler(scaler)
            if scaler_obj is not None:
                # Fit apenas no treino; transform no treino/teste.
                X_train = pd.DataFrame(scaler_obj.fit_transform(X_train_raw), columns=selected_features, index=X_train_raw.index)
                X_test = pd.DataFrame(scaler_obj.transform(X_test_raw), columns=selected_features, index=X_test_raw.index)
            else:
                X_train = X_train_raw
                X_test = X_test_raw

            model_obj, resolved_type = _make_model(model_type, target_kind, random_state)

            if model_type == "ensemble_basic":
                for _, component, _ in model_obj:
                    component.fit(X_train, y_train)
                pred, proba = _ensemble_predict(model_obj, X_test, target_kind)
                trained_payload_model = model_obj
            else:
                model_obj.fit(X_train, y_train)
                pred = model_obj.predict(X_test)
                proba = None
                if target_kind == "classification":
                    try:
                        proba = model_obj.predict_proba(X_test)
                    except Exception:
                        proba = None
                trained_payload_model = model_obj

            if target_kind == "regression":
                metrics = _regression_metrics(pd.to_numeric(y_test, errors="coerce"), pred)
            else:
                metrics = _classification_metrics(y_test, pred, proba)

            train_start = str(train_df["date"].min().date())
            train_end = str(train_df["date"].max().date())
            test_start = str(test_df["date"].min().date())
            test_end = str(test_df["date"].max().date())

            # Feature importance final.
            importance = {}
            if model_type == "ensemble_basic":
                accum = {f: 0.0 for f in selected_features}
                for _, component, weight in trained_payload_model:
                    if hasattr(component, "feature_importances_"):
                        for f, v in zip(selected_features, component.feature_importances_):
                            accum[f] += float(v) * float(weight)
                importance = dict(sorted(accum.items(), key=lambda kv: kv[1], reverse=True))
            elif hasattr(trained_payload_model, "feature_importances_"):
                importance = {
                    f: float(v)
                    for f, v in sorted(zip(selected_features, trained_payload_model.feature_importances_), key=lambda x: x[1], reverse=True)
                }
            elif selection_importance:
                importance = dict(sorted(selection_importance.items(), key=lambda kv: kv[1], reverse=True))

            metrics.update({
                "split_mode": split_mode,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "target_type": target_kind,
                "rows_train": int(len(train_df)),
                "rows_test": int(len(test_df)),
                "scaler_type": scaler,
                "scaler_fit_scope": "train_only",
                "feature_selection_method": feature_selection,
                "selected_features": selected_features,
                "removed_features": removed_features,
                "top_features": int(top_features),
                "correlation_threshold": float(correlation_threshold),
                "leakage_checks_passed": bool(leakage_passed),
                "leakage_warnings": leakage_warnings,
                "ensemble_components": [
                    {"name": name, "weight": weight}
                    for name, _, weight in trained_payload_model
                ] if model_type == "ensemble_basic" else [],
            })

            mlflow_tracking_status = "not_configured"
            try:
                import mlflow
                import mlflow.sklearn
                mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
                mlflow.set_experiment(f"financeos_{ds.get('asset_class')}_{target}")
                with mlflow.start_run(run_name=f"{resolved_type}_{dataset_id}"):
                    mlflow.log_params({
                        "model_type": resolved_type,
                        "dataset_id": dataset_id,
                        "target": target,
                        "target_type": target_kind,
                        "asset_class": ds.get("asset_class"),
                        "split_mode": split_mode,
                        "scaler": scaler,
                        "feature_selection": feature_selection,
                        "top_features": top_features,
                        "correlation_threshold": correlation_threshold,
                    })
                    numeric_metrics = {k: v for k, v in metrics.items() if isinstance(v, (int, float)) and v is not None}
                    if numeric_metrics:
                        mlflow.log_metrics(numeric_metrics)
                    if model_type == "ensemble_basic":
                        # loga o primeiro componente como referência; payload completo é salvo localmente.
                        mlflow.sklearn.log_model(trained_payload_model[0][1], artifact_path="model_component_0")
                    else:
                        mlflow.sklearn.log_model(trained_payload_model, artifact_path="model")
                mlflow_tracking_status = "logged"
            except Exception as mlflow_exc:
                mlflow_tracking_status = f"failed:{mlflow_exc}"

            metrics["mlflow_tracking_status"] = mlflow_tracking_status

            model_name = f"{resolved_type}_dataset_{dataset_id}_{now_iso().replace(':','-')}.pkl"
            model_path = MODELS_DIR / model_name
            payload = {
                "model": trained_payload_model,
                "features": selected_features,
                "raw_features": features,
                "removed_features": removed_features,
                "target": target,
                "target_type": target_kind,
                "dataset_id": dataset_id,
                "model_type": resolved_type,
                "scaler": scaler_obj,
                "scaler_type": scaler,
                "feature_selection_method": feature_selection,
                "ensemble_weights": [0.5, 0.5] if model_type == "ensemble_basic" else None,
            }
            with open(model_path, "wb") as f:
                pickle.dump(payload, f)

            cur = conn.execute(
                """
                INSERT INTO ml_models (
                    dataset_id, model_name, model_type, target_name, asset_class,
                    train_start, train_end, test_start, test_end,
                    metrics_json, feature_importance_json, model_path, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id, model_name, resolved_type, target, ds.get("asset_class"),
                    train_start, train_end, test_start, test_end,
                    json_dump(metrics), json_dump(importance), str(model_path), "trained", now_iso(),
                ),
            )
            model_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO ml_model_evaluations (
                    model_id, evaluation_date, split_mode, target_name, metrics_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (model_id, now_iso(), split_mode, target, json_dump(metrics), now_iso()),
            )
            conn.commit()

            result = {
                "model_id": model_id,
                "model_path": str(model_path),
                "target_type": target_kind,
                "split_mode": split_mode,
                "scaler": scaler,
                "feature_selection": feature_selection,
                "selected_features": selected_features,
                "removed_features": removed_features,
                "leakage_checks_passed": bool(leakage_passed),
                "leakage_warnings": leakage_warnings,
                "metrics": metrics,
                "feature_importance": importance,
            }
            finish_ml_run(conn, run_id, "success", result)
            return result
        except Exception as exc:
            finish_ml_run(conn, run_id, "failed", {}, str(exc))
            raise
