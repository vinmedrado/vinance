
from __future__ import annotations

from db import pg_compat as dbcompat

import altair as alt
import pandas as pd
import streamlit as st

from services.intelligence_bi_service import (
    build_executive_reading,
    build_intelligence_dataframe,
    calculate_bi_kpis,
    calculate_moving_average,
    load_intelligence_history,
    prepare_alerts_series,
    prepare_opportunities_series,
    prepare_trend_distribution,
)
from services.ui_helpers import ROOT_DIR
from services.ui_components import inject_global_css, render_metric_card, render_section_header

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · BI da Inteligência", layout="wide")
inject_global_css()

st.title("BI da Inteligência")
st.caption("Evolução histórica, tendência e qualidade do sistema.")

if not ROOT_DIR.exists():
    st.error(f"Banco não encontrado: {ROOT_DIR}")
    st.stop()

with dbcompat.connect(ROOT_DIR) as conn:
    runs = load_intelligence_history(conn)

df = build_intelligence_dataframe(runs)

if df.empty:
    st.warning("Ainda não há histórico inteligente suficiente. Rode o Orquestrador Geral para gerar dados.")
    st.page_link("legacy_streamlit/pages/13_Orquestrador_Geral.py", label="Abrir Orquestrador Geral", icon="🚀")
    st.stop()

render_section_header("Filtros")
f1, f2, f3, f4 = st.columns(4)

with f1:
    trends = ["all"] + sorted([str(x) for x in df["trend"].dropna().unique()])
    trend_filter = st.selectbox("Trend", trends, index=0)
with f2:
    min_score = st.number_input("Score mínimo", min_value=0.0, max_value=100.0, value=0.0, step=5.0)
with f3:
    max_score = st.number_input("Score máximo", min_value=0.0, max_value=100.0, value=100.0, step=5.0)
with f4:
    ma_window = st.selectbox("Média móvel", [3, 5], index=1)

date_min = df["data"].min()
date_max = df["data"].max()
d1, d2 = st.columns(2)
with d1:
    start_date = st.date_input("Data inicial", value=date_min.date() if pd.notna(date_min) else None)
with d2:
    end_date = st.date_input("Data final", value=date_max.date() if pd.notna(date_max) else None)

filtered = df.copy()
if trend_filter != "all":
    filtered = filtered[filtered["trend"] == trend_filter]
filtered = filtered[(filtered["score"].fillna(0) >= float(min_score)) & (filtered["score"].fillna(0) <= float(max_score))]
if start_date:
    filtered = filtered[filtered["data"] >= pd.to_datetime(start_date)]
if end_date:
    filtered = filtered[filtered["data"] <= pd.to_datetime(end_date) + pd.Timedelta(days=1)]

if filtered.empty:
    st.warning("Nenhum registro encontrado com os filtros atuais.")
    st.stop()

filtered = calculate_moving_average(filtered, window=int(ma_window))
kpis = calculate_bi_kpis(filtered)

def _trend_color(trend: str | None) -> str:
    if trend == "improving":
        return "green"
    if trend == "worsening":
        return "red"
    return "yellow"

render_section_header("KPIs Principais")
k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
with k1:
    render_metric_card("Último Score", kpis["last_score"] if kpis["last_score"] is not None else "-", color=_trend_color(kpis.get("current_trend")))
with k2:
    delta = kpis.get("last_delta")
    render_metric_card("Delta", "-" if delta is None else f"{delta:+.1f}", color="green" if (delta or 0) > 0 else "red" if (delta or 0) < 0 else "yellow")
with k3:
    render_metric_card("Tendência", kpis.get("current_trend") or "-", color=_trend_color(kpis.get("current_trend")))
with k4:
    render_metric_card("Melhor Score", kpis["best_score"] if kpis["best_score"] is not None else "-", color="green")
with k5:
    render_metric_card("Pior Score", kpis["worst_score"] if kpis["worst_score"] is not None else "-", color="red")
with k6:
    render_metric_card("Média últimos 5", kpis["avg_last_5"] if kpis["avg_last_5"] is not None else "-", color="blue")
with k7:
    render_metric_card("Execuções", kpis["total_runs"], color="purple")

render_section_header("Leitura Executiva")
reading = build_executive_reading(filtered, kpis)
if kpis.get("current_trend") == "improving":
    st.success(reading)
elif kpis.get("current_trend") == "worsening":
    st.error(reading)
else:
    st.warning(reading)

render_section_header("Gráficos")

score_df = filtered.sort_values("data").copy()
ma_col = f"ma_{int(ma_window)}"

score_base = alt.Chart(score_df).encode(x=alt.X("data:T", title="Data"))
score_line = score_base.mark_line(point=True).encode(
    y=alt.Y("score:Q", title="Score Global"),
    tooltip=["run_id", "data", "score", "delta", "trend", "label"],
)
ma_line = score_base.mark_line(strokeDash=[6, 4]).encode(
    y=alt.Y(f"{ma_col}:Q", title="Média móvel"),
    tooltip=["run_id", "data", ma_col],
)
st.altair_chart((score_line + ma_line).properties(title="Evolução do Score Global", height=320), use_container_width=True)

delta_chart = alt.Chart(score_df).mark_bar().encode(
    x=alt.X("data:T", title="Data"),
    y=alt.Y("delta:Q", title="Delta"),
    color=alt.condition(
        alt.datum.delta > 0,
        alt.value("#2E7D32"),
        alt.condition(alt.datum.delta < 0, alt.value("#C62828"), alt.value("#F9A825")),
    ),
    tooltip=["run_id", "data", "delta", "trend"],
).properties(title="Delta entre Execuções", height=280)
st.altair_chart(delta_chart, use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    trend_df = prepare_trend_distribution(filtered)
    trend_chart = alt.Chart(trend_df).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("count:Q"),
        color=alt.Color("trend:N", legend=alt.Legend(title="Trend")),
        tooltip=["trend", "count"],
    ).properties(title="Distribuição de Tendências", height=300)
    st.altair_chart(trend_chart, use_container_width=True)

with c2:
    alerts_df = prepare_alerts_series(filtered)
    alerts_chart = alt.Chart(alerts_df).mark_line(point=True).encode(
        x=alt.X("data:T", title="Data"),
        y=alt.Y("alertas:Q", title="Alertas"),
        tooltip=["data", "alertas", "warnings", "top_insights"],
    ).properties(title="Alertas ao Longo do Tempo", height=300)
    st.altair_chart(alerts_chart, use_container_width=True)

opp_df = prepare_opportunities_series(filtered)
opp_chart = alt.Chart(opp_df).mark_line(point=True).encode(
    x=alt.X("data:T", title="Data"),
    y=alt.Y("oportunidades:Q", title="Oportunidades"),
    tooltip=["data", "oportunidades"],
).properties(title="Oportunidades ao Longo do Tempo", height=280)
st.altair_chart(opp_chart, use_container_width=True)

with st.expander("Ver histórico detalhado", expanded=False):
    cols = [
        "run_id", "data", "score", "delta", "trend", "label",
        "alertas", "oportunidades", "resumo",
    ]
    table = filtered[cols].sort_values("data", ascending=False).copy()
    st.dataframe(table, use_container_width=True, hide_index=True)

with st.expander("Dados brutos do BI"):
    st.dataframe(filtered, use_container_width=True, hide_index=True)
