from __future__ import annotations

import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import money, month_ref, seed_demo_if_empty, summarize_month
from services.financial_intelligence_service import build_financial_diagnosis
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_callout, render_empty_state

st.set_page_config(page_title="FinanceOS · Visão Financeira", layout="wide")
inject_global_css()
check_auth()

try:
    seed_demo_if_empty()
except Exception:
    render_callout("Banco financeiro indisponível", "Configure DATABASE_URL/SYNC_DATABASE_URL para carregar a visão financeira.", "warning")
    st.stop()

render_hero(
    "Visão financeira inteligente",
    "Receitas, despesas, orçamento, investimentos e alertas em uma visão mensal clara para usuário final.",
    eyebrow="Financeiro",
    status="ERP + orçamento + investimentos conectados",
)

selected_month = st.text_input("Mês de referência", value=month_ref())
summary = summarize_month(month=selected_month)
diagnosis = build_financial_diagnosis(month=selected_month)

c1, c2, c3, c4, c5 = st.columns(5)
with c1: render_metric_card("Receitas", money(summary['income']), "Recebido no mês", "green")
with c2: render_metric_card("Despesas", money(summary['expenses']), "Realizado", "red" if summary['expenses'] > summary['income'] else "yellow")
with c3: render_metric_card("Sobra disponível", money(summary['available_to_invest']), "Após gastos e aportes", "green" if summary['available_to_invest'] >= 0 else "red")
with c4: render_metric_card("% investido", f"{summary['percent_invested']:.1f}%", "Sobre renda base", "blue")
with c5: render_metric_card("Score", f"{diagnosis['score']}/100", diagnosis['label'], "purple")

render_section_header("Diagnóstico do mês")
cols = st.columns(3)
with cols[0]: render_callout("Maior categoria", f"{summary['biggest_category']} concentra o maior gasto do mês.", "info")
with cols[1]: render_callout("Meta de investimento", f"Sugestão mensal: {money(summary['recommended_investment'])}. Gap atual: {money(summary['investment_gap'])}.", "success" if summary['investment_gap'] >= 0 else "warning")
with cols[2]: render_callout("Próximo passo", "Abra o diagnóstico para ver alertas, previsão de fechamento e oportunidades de economia.", "info")

render_section_header("Gastos por categoria")
df = pd.DataFrame([{"Categoria": k, "Valor": v} for k, v in summary['by_category'].items()])
if df.empty:
    render_empty_state("Sem dados financeiros", "Cadastre receitas e despesas para ativar gráficos, orçamento e inteligência financeira.", "Cadastrar despesas", "legacy_streamlit/pages/03_Despesas.py")
else:
    st.bar_chart(df.set_index('Categoria'))
    st.dataframe(df.assign(Valor=df['Valor'].map(money)), use_container_width=True, hide_index=True)

render_section_header("Atalhos do fluxo")
a, b, c = st.columns(3)
with a: st.page_link("legacy_streamlit/pages/03_Despesas.py", label="Cadastrar despesas", icon="💳")
with b: st.page_link("legacy_streamlit/pages/04_Orcamento.py", label="Ajustar orçamento", icon="📊")
with c: st.page_link("legacy_streamlit/pages/05_Diagnostico_Financeiro.py", label="Ver diagnóstico", icon="✨")
