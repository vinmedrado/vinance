from __future__ import annotations
import streamlit as st
from services.i18n_service import language_selector
from services.auth_middleware import check_auth
from services.ui_components import inject_global_css, render_hero, render_callout

st.set_page_config(page_title="FinanceOS · Onboarding", layout="wide")
inject_global_css()
user = check_auth()
language_selector()
render_hero("Onboarding financeiro", "Configure renda, orçamento, perfil de risco e mercados para personalizar a experiência.", eyebrow="Primeiros passos")

c1,c2,c3 = st.columns(3)
with c1:
    currency = st.selectbox("Moeda preferida", ["BRL", "USD", "EUR", "BTC"])
    income = st.number_input("Renda mensal estimada", min_value=0.0, value=6500.0, step=100.0)
with c2:
    budget = st.selectbox("Modelo de orçamento", ["50/30/20", "70/20/10", "60/30/10", "Base Zero", "Personalizado Premium"])
    risk = st.radio("Perfil", ["Conservador", "Moderado", "Arrojado"], horizontal=True)
with c3:
    markets = st.multiselect("Mercados", ["Ações B3", "US Equities", "ETFs", "FIIs/REITs", "Cripto", "Forex"], default=["Ações B3"])
    st.file_uploader("Importação opcional", type=["xlsx", "csv"])
render_callout("Produto integrado", "Despesas, orçamento e investimentos serão usados como base para alertas, diagnósticos e sugestões futuras.", "info")
if st.button("Finalizar onboarding", type="primary"):
    st.session_state["user"]["preferred_currency"] = currency
    st.session_state["user"]["onboarding_completed"] = True
    st.success("Onboarding concluído.")
    st.switch_page("legacy_streamlit/main_streamlit.py")
