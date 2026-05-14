
from __future__ import annotations

import json
from db import pg_compat as dbcompat

import pandas as pd
import streamlit as st

from services.ml_common import ROOT_DIR, bootstrap_ml_tables, connect, json_load
from services.ml_dataset_service import build_dataset, list_datasets
from services.ml_training_service import train_model
from services.ml_prediction_service import predict, latest_predictions
from services.ml_model_registry import list_models, get_best_model, ml_overview
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
st.set_page_config(page_title="FinanceOS · Machine Learning", layout="wide")
inject_global_css()

st.title("Machine Learning")
st.caption("ML por trás do FinanceOS: previsão, ranking e score futuro. Backtest continua sendo a validação principal.")
st.info("Segurança: o ML não compra/vende, não altera estratégia e não substitui o backtest. Ele apenas recomenda e ranqueia ativos.")

with connect() as conn:
    bootstrap_ml_tables(conn)

overview = ml_overview()

render_section_header("Visão geral ML")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    render_metric_card("Datasets", overview["datasets"], color="blue")
with c2:
    render_metric_card("Modelos", overview["models"], color="purple")
with c3:
    render_metric_card("Previsões", overview["predictions"], color="green")
with c4:
    last_model = overview.get("last_model") or {}
    render_metric_card("Último modelo", last_model.get("id", "-"), color="blue")
with c5:
    best = overview.get("best_model") or {}
    render_metric_card("Melhor modelo", best.get("id", "-"), color="green")

if best:
    st.caption(f"Melhor modelo detectado: #{best.get('id')} · {best.get('model_type')} · métricas={json_load(best.get('metrics_json'))}")

tabs = st.tabs(["Criar Dataset", "Treinar Modelo", "Gerar Previsões", "Resultados", "Comparar ML com Backtest"])

with tabs[0]:
    render_section_header("Criar Dataset")
    d1, d2, d3 = st.columns(3)
    with d1:
        asset_class = st.selectbox("asset_class", ["all", "equity", "fii", "etf", "bdr", "crypto", "index", "unknown"], index=0)
        target = st.selectbox(
            "target",
            ["future_return_positive", "future_return_regression", "future_return_class"],
            index=0,
            help="Classificação binária, regressão de retorno real ou classes low/medium/high.",
        )
    with d2:
        start_date = st.text_input("start_date", value="2020-01-01")
        end_date = st.text_input("end_date", value="")
        horizon_days = st.number_input("horizon_days", min_value=1, max_value=252, value=21, step=1)
    with d3:
        min_quality_score = st.number_input("min_quality_score", min_value=0.0, max_value=100.0, value=45.0, step=5.0)
        min_history_days = st.number_input("min_history_days", min_value=1, max_value=2000, value=180, step=30)

    if target == "future_return_regression":
        st.info("Target de regressão: o modelo prevê retorno futuro esperado.")
    elif target == "future_return_class":
        st.info("Target multiclasse: low <= 0%, medium até 5%, high > 5%.")
    else:
        st.info("Target binário: probabilidade de retorno futuro positivo.")

    if st.button("Criar Dataset", type="primary", use_container_width=True):
        try:
            with st.spinner("Construindo dataset ML com filtros de qualidade..."):
                result = build_dataset(
                    asset_class=asset_class,
                    start_date=start_date or None,
                    end_date=end_date or None,
                    target=target,
                    horizon_days=int(horizon_days),
                    min_quality_score=float(min_quality_score),
                    min_history_days=int(min_history_days),
                )
            st.success(f"Dataset criado: #{result['dataset_id']} · {result['rows']} linhas")
            if result["rows"] < 200:
                st.warning("Dataset possui poucos dados. Métricas podem ficar instáveis.")
            st.json(result)
        except Exception as exc:
            st.error(str(exc))

    datasets = list_datasets(50)
    if datasets:
        st.markdown("### Datasets recentes")
        st.dataframe(pd.DataFrame(datasets), use_container_width=True, hide_index=True)

with tabs[1]:
    render_section_header("Treinar Modelo")
    datasets = list_datasets(100)
    if not datasets:
        st.warning("Nenhum dataset criado ainda.")
    else:
        dataset_options = {f"#{d['id']} · {d['target_name']} · {d['rows_count']} linhas": int(d["id"]) for d in datasets}
        selected_dataset = st.selectbox("Dataset", list(dataset_options.keys()))
        ds_id = dataset_options[selected_dataset]
        ds_row = next((d for d in datasets if int(d["id"]) == ds_id), {})
        target_name = ds_row.get("target_name")
        target_type = "regressão" if target_name == "future_return_regression" else "classificação"
        st.info(f"Tipo detectado: {target_type}. O sistema usará regressor para regressão e classifier para classificação.")

        model_type = st.selectbox("model_type", ["random_forest", "gradient_boosting", "ensemble_basic"], index=0)
        t1, t2, t3 = st.columns(3)
        with t1:
            test_size = st.number_input("test_size", min_value=0.1, max_value=0.5, value=0.2, step=0.05)
            scaler = st.selectbox("scaler", ["standard", "minmax", "none"], index=0)
        with t2:
            random_state = st.number_input("random_state", min_value=1, max_value=9999, value=42, step=1)
            feature_selection = st.selectbox("feature_selection", ["none", "importance", "correlation"], index=0)
        with t3:
            split_mode = st.selectbox("split_mode", ["temporal", "random"], index=0)
            top_features = st.number_input("top_features", min_value=1, max_value=100, value=20, step=1)
            correlation_threshold = st.number_input("correlation_threshold", min_value=0.5, max_value=1.0, value=0.95, step=0.01)

        if split_mode == "temporal":
            st.success("Modelo validado em período futuro, mais confiável que split aleatório.")
        else:
            st.warning("Split aleatório pode inflar métricas em séries temporais. Use para diagnóstico, não como validação principal.")

        if st.button("Treinar Modelo", type="primary", use_container_width=True):
            try:
                with st.spinner("Treinando modelo ML..."):
                    result = train_model(
                        dataset_id=ds_id,
                        model_type=model_type,
                        test_size=float(test_size),
                        random_state=int(random_state),
                        split_mode=split_mode,
                        scaler=scaler,
                        feature_selection=feature_selection,
                        top_features=int(top_features),
                        correlation_threshold=float(correlation_threshold),
                    )
                st.success(f"Modelo treinado: #{result['model_id']}")
                st.json(result)
            except Exception as exc:
                st.error(str(exc))

    models = list_models(50)
    if models:
        st.markdown("### Modelos recentes")
        rows = []
        for m in models:
            metrics = json_load(m.get("metrics_json"))
            rows.append({
                "id": m.get("id"),
                "dataset_id": m.get("dataset_id"),
                "model_type": m.get("model_type"),
                "target": m.get("target_name"),
                "split_mode": metrics.get("split_mode"),
                "train": f"{metrics.get('train_start')} → {metrics.get('train_end')}",
                "test": f"{metrics.get('test_start')} → {metrics.get('test_end')}",
                "scaler": metrics.get("scaler_type"),
                "feature_selection": metrics.get("feature_selection_method"),
                "leakage_ok": metrics.get("leakage_checks_passed"),
                "metrics": metrics,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with st.expander("Leakage checks e features selecionadas"):
            for m in models[:10]:
                metrics = json_load(m.get("metrics_json"))
                st.markdown(f"**Modelo #{m.get('id')} · {m.get('model_type')}**")
                if metrics.get("leakage_checks_passed") is True:
                    st.success("Leakage checks passaram.")
                elif metrics.get("leakage_checks_passed") is False:
                    st.error("Leakage checks falharam ou geraram alerta forte.")
                else:
                    st.info("Modelo antigo sem leakage checks.")
                if metrics.get("leakage_warnings"):
                    st.warning(metrics.get("leakage_warnings"))
                st.caption(f"Scaler: {metrics.get('scaler_type', 'legacy')} · Feature selection: {metrics.get('feature_selection_method', 'legacy')}")
                st.write("Selected features:", metrics.get("selected_features", []))
                st.write("Removed features:", metrics.get("removed_features", []))

        selected_model_features = st.selectbox("Ver Top 10 features do modelo", [f"#{m['id']} · {m['model_type']}" for m in models], key="features_model")
        selected_id = int(selected_model_features.split("·")[0].replace("#", "").strip())
        model_row = next((m for m in models if int(m["id"]) == selected_id), None)
        if model_row:
            importance = json_load(model_row.get("feature_importance_json"))
            if importance:
                top = pd.DataFrame([{"feature": k, "importance": v} for k, v in list(importance.items())[:10]])
                st.dataframe(top, use_container_width=True, hide_index=True)
            else:
                st.info("Modelo não possui feature_importances_ disponível.")

with tabs[2]:
    render_section_header("Gerar Previsões")
    models = list_models(100)
    if not models:
        st.warning("Nenhum modelo treinado ainda.")
    else:
        model_options = {f"#{m['id']} · {m['model_type']} · {m['target_name']}": int(m["id"]) for m in models}
        selected_model = st.selectbox("Modelo", list(model_options.keys()))
        selected_model_id = model_options[selected_model]
        model_info = next((m for m in models if int(m["id"]) == selected_model_id), {})
        target_name = model_info.get("target_name")
        st.info("Classificação: predicted_score = probabilidade da classe positiva/high. Regressão: predicted_score = retorno previsto.")

        p1, p2, p3 = st.columns(3)
        with p1:
            pred_asset_class = st.selectbox("asset_class previsão", ["all", "equity", "fii", "etf", "bdr", "crypto", "index", "unknown"], index=0)
            limit = st.number_input("limit", min_value=1, max_value=1000, value=50, step=10)
        with p2:
            pred_min_quality = st.number_input("min_quality_score previsão", min_value=0.0, max_value=100.0, value=45.0, step=5.0)
        with p3:
            pred_min_history = st.number_input("min_history_days previsão", min_value=1, max_value=2000, value=180, step=30)

        if st.button("Gerar Previsões", type="primary", use_container_width=True):
            try:
                with st.spinner("Gerando previsões ML com filtros..."):
                    result = predict(
                        model_id=selected_model_id,
                        asset_class=pred_asset_class,
                        limit=int(limit),
                        min_quality_score=float(pred_min_quality),
                        min_history_days=int(pred_min_history),
                    )
                st.success(f"Previsões geradas: {result['predictions']}")
                if result.get("removed_by_filters", 0) > 0:
                    st.warning(f"{result['removed_by_filters']} ativo(s) removidos por qualidade/histórico insuficiente.")
                st.json(result)
            except Exception as exc:
                st.error(str(exc))

with tabs[3]:
    render_section_header("Top ativos previstos")
    predictions = latest_predictions(limit=200)
    if not predictions:
        st.info("Nenhuma previsão gerada ainda.")
    else:
        rows = []
        for p in predictions:
            exp = json_load(p.get("explanation_json"))
            feats = json_load(p.get("features_json"))
            rows.append({
                "ticker": p.get("ticker"),
                "model_id": p.get("model_id"),
                "prediction_date": p.get("prediction_date"),
                "predicted_score": p.get("predicted_score"),
                "predicted_label": p.get("predicted_label"),
                "confidence": p.get("confidence"),
                "data_quality_score": feats.get("data_quality_score"),
                "history_days": feats.get("history_days"),
                "explanation": exp.get("summary"),
            })
        df = pd.DataFrame(rows)
        def _rec(row):
            exp = json_load(next((p.get("explanation_json") for p in predictions if p.get("ticker") == row["ticker"] and p.get("model_id") == row["model_id"]), "{}"))
            return exp.get("recommendation") or "Neutra"
        df["recommendation"] = df.apply(_rec, axis=1)
        df = df.sort_values(["confidence", "predicted_score", "data_quality_score"], ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        st.markdown("### Ranking visual Top 10")
        top10 = df.head(10)
        for _, row in top10.iterrows():
            badge = row["recommendation"]
            color = "green" if badge == "Forte" else "blue" if badge == "Boa" else "red" if badge == "Evitar" else "yellow"
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    render_metric_card("Rank", int(row["rank"]), color=color)
                with c2:
                    render_metric_card("Ticker", row["ticker"], color=color)
                with c3:
                    render_metric_card("Score", f"{float(row['predicted_score']):.4f}", color=color)
                with c4:
                    render_metric_card("Confiança", f"{float(row['confidence']):.2f}", color=color)
                with c5:
                    render_metric_card("Recomendação", badge, color=color)
                st.caption(row.get("explanation") or "")

        st.markdown("### Tabela completa de previsões")
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("Features usadas e explicações"):
            for p in predictions[:30]:
                exp = json_load(p.get("explanation_json"))
                feats = json_load(p.get("features_json"))
                st.markdown(f"**{p.get('ticker')}** · score={float(p.get('predicted_score') or 0):.4f} · confiança={float(p.get('confidence') or 0):.2f} · {exp.get('recommendation', 'Neutra')}")
                st.write(exp.get("summary"))
                st.json({"features": feats, "explanation": exp})

with tabs[4]:
    render_section_header("Comparar ML com Backtest")
    predictions = latest_predictions(limit=100)
    if not predictions:
        st.info("Gere previsões primeiro.")
    else:
        pred_df = pd.DataFrame(predictions)
        pred_df["predicted_score"] = pd.to_numeric(pred_df["predicted_score"], errors="coerce")
        pred_df = pred_df.sort_values("predicted_score", ascending=False).head(50)

        comparison = pred_df[["ticker", "model_id", "predicted_score", "predicted_label", "confidence"]].copy()
        comparison["appears_in_backtest_recent"] = False
        comparison["backtest_note"] = "Comparação automática depende de tabela/ranking de backtest disponível."

        try:
            with dbcompat.connect(ROOT_DIR) as conn:
                conn.row_factory = dbcompat.Row
                tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                candidate_tables = [t for t in tables if "backtest" in t.lower() or "rank" in t.lower() or "score" in t.lower()]
                found_tickers = set()
                for t in candidate_tables:
                    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
                    ticker_col = next((c for c in ["ticker", "symbol", "asset", "asset_symbol"] if c in cols), None)
                    if ticker_col:
                        rows = conn.execute(f"SELECT DISTINCT {ticker_col} AS ticker FROM {t} LIMIT 500").fetchall()
                        found_tickers.update(str(r["ticker"]) for r in rows if r["ticker"])
                if found_tickers:
                    comparison["appears_in_backtest_recent"] = comparison["ticker"].astype(str).isin(found_tickers)
                    comparison["backtest_note"] = comparison["appears_in_backtest_recent"].map(lambda x: "Encontrado em tabela/ranking recente." if x else "Não encontrado em ranking/tabela recente.")
        except Exception as exc:
            comparison["backtest_note"] = f"Erro ao comparar: {exc}"

        st.dataframe(comparison, use_container_width=True, hide_index=True)
        st.warning("Backtest continua sendo a validação principal. ML aqui é score/ranking auxiliar para análise futura.")
