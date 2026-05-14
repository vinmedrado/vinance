from __future__ import annotations

import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import create_goal, list_goals, money, seed_demo_if_empty, summarize_month
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout

st.set_page_config(page_title="FinanceOS · Metas", layout="wide")
inject_global_css()
check_auth()
try:
    seed_demo_if_empty()
except Exception:
    render_callout("Banco indisponível", "Configure o banco para cadastrar metas reais.", "warning")
    st.stop()

render_hero("Metas financeiras", "Conecte objetivos pessoais à sobra mensal, orçamento e aportes planejados.", eyebrow="ERP Financeiro")
with st.container(border=True):
    c1,c2,c3 = st.columns(3)
    with c1: name = st.text_input("Meta", placeholder="Reserva de emergência")
    with c2: target = st.number_input("Valor alvo", min_value=0.0, step=100.0)
    with c3: current = st.number_input("Valor atual", min_value=0.0, step=100.0)
    if st.button("Salvar meta", type="primary"):
        if name and target > 0:
            create_goal(name, target, current)
            st.success("Meta salva.")
            st.rerun()
        else:
            st.warning("Informe nome e valor alvo.")

goals = list_goals()
summary = summarize_month()
c1,c2,c3 = st.columns(3)
with c1: render_metric_card("Sobra disponível", money(summary['available_to_invest']), color="green")
with c2: render_metric_card("Aporte sugerido", money(summary['recommended_investment']), color="purple")
with c3: render_metric_card("Metas ativas", len(goals), color="blue")
render_section_header("Lista de metas")
if goals:
    df = pd.DataFrame(goals)
    df["progresso_%"] = df.apply(lambda r: round(float(r.get("current_amount") or 0) / float(r.get("target_amount") or 1) * 100, 1), axis=1)
    df["target_amount"] = df["target_amount"].map(money)
    df["current_amount"] = df["current_amount"].map(money)
    st.dataframe(df[["id","name","target_amount","current_amount","progresso_%","status"]], use_container_width=True, hide_index=True)
else:
    render_empty_state("Nenhuma meta cadastrada", "Crie uma meta para transformar economia mensal em evolução patrimonial.")
