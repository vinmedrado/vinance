from __future__ import annotations

import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import BUDGET_MODELS, calculate_budget, money, month_ref, seed_demo_if_empty, summarize_month, upsert_budget_profile
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_callout, render_badge

st.set_page_config(page_title="FinanceOS · Orçamento", layout="wide")
inject_global_css()
check_auth()

try:
    seed_demo_if_empty()
except Exception:
    render_callout("Banco financeiro indisponível", "Configure o banco para salvar o orçamento real.", "warning")
    st.stop()

render_hero(
    "Orçamento conectado aos investimentos",
    "Escolha um modelo, salve a renda mensal e compare planejado vs. realizado com base nas despesas reais do banco.",
    eyebrow="Planejamento financeiro",
    status="50/30/20 · 70/20/10 · 60/30/10 · Base Zero · Personalizado",
)

summary = summarize_month(month=month_ref())
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        income = st.number_input("Renda mensal", min_value=0.0, value=float(summary.get("income_base") or summary.get("income") or 6500), step=100.0)
    with c2:
        model = st.selectbox("Modelo", list(BUDGET_MODELS.keys()), index=list(BUDGET_MODELS.keys()).index(summary.get("budget_model", "50/30/20")) if summary.get("budget_model") in BUDGET_MODELS else 0)
    with c3:
        if st.button("Salvar orçamento", type="primary", use_container_width=True):
            upsert_budget_profile(model, income)
            st.success("Orçamento salvo no banco.")
            st.rerun()

rows = calculate_budget(model, income, summary['by_category'])
df = pd.DataFrame(rows)
invest_limit = next((r['Planejado'] for r in rows if 'Investimentos' in r['Categoria']), 0)
invest_real = summary['invested']

c1, c2, c3, c4 = st.columns(4)
with c1: render_metric_card("Modelo ativo", model, color="blue")
with c2: render_metric_card("Meta para investir", money(invest_limit), color="green")
with c3: render_metric_card("Investido real", money(invest_real), "Aportes do mês", "purple")
with c4: render_metric_card("Diferença", money(invest_real - invest_limit), "Real - planejado", "green" if invest_real >= invest_limit else "yellow")

render_section_header("Planejado vs. realizado")
view = df.copy()
view["Percentual"] = view["Percentual"].map(lambda v: f"{float(v):.0%}")
for col in ['Planejado', 'Realizado', 'Diferença']:
    view[col] = view[col].map(money)
st.dataframe(view, use_container_width=True, hide_index=True)

render_section_header("Sugestões inteligentes")
cols = st.columns(2)
for idx, row in enumerate(rows):
    with cols[idx % 2]:
        if row['Diferença'] < 0:
            render_callout(row['Categoria'], f"Você passou {money(abs(row['Diferença']))} do limite. Revise recorrências e gastos dessa categoria.", "warning")
        else:
            render_callout(row['Categoria'], f"Ainda há {money(row['Diferença'])} disponível nesse bloco do orçamento.", "success")

st.caption("Investimentos fazem parte do planejamento financeiro e alimentam carteira, alertas e diagnóstico. Não é recomendação financeira.")
