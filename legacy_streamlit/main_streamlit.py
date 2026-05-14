from __future__ import annotations

import os
import streamlit as st

from services.ui_components import (
    inject_global_css,
    render_hero,
    render_metric_card,
    render_section_header,
    render_empty_state,
    render_callout,
)

st.set_page_config(page_title="FinanceOS · ERP Financeiro Inteligente", page_icon="💎", layout="wide")
inject_global_css()

ENV = os.getenv("FINANCEOS_ENV", "development").lower()
DEV_MODE = os.getenv("FINANCEOS_DEV_MODE", "true").lower() == "true" and ENV != "production"

if "financeos_mode" not in st.session_state:
    st.session_state["financeos_mode"] = "Investidor"

with st.sidebar:
    st.markdown("### FinanceOS")
    if DEV_MODE:
        st.info("Modo Demo ativo")
    mode = st.radio("Área", ["Investidor", "Admin"], key="financeos_mode", horizontal=False)
    st.divider()
    st.markdown("**FINANCEIRO**")
    st.page_link("legacy_streamlit/pages/02_Financeiro_Visao_Geral.py", label="Visão Geral", icon="🏠")
    st.page_link("legacy_streamlit/pages/06_Receitas.py", label="Receitas", icon="💰")
    st.page_link("legacy_streamlit/pages/03_Despesas.py", label="Despesas", icon="💳")
    st.page_link("legacy_streamlit/pages/04_Orcamento.py", label="Orçamento", icon="📊")
    st.page_link("legacy_streamlit/pages/07_Metas.py", label="Metas", icon="🎯")
    st.markdown("**INVESTIMENTOS**")
    st.page_link("legacy_streamlit/pages/20_Minha_Carteira.py", label="Minha Carteira", icon="💼")
    st.page_link("legacy_streamlit/pages/19_Oportunidades_Mercado.py", label="Oportunidades", icon="📈")
    st.page_link("legacy_streamlit/pages/21_Meus_Alertas.py", label="Alertas", icon="🔔")
    st.markdown("**INTELIGÊNCIA**")
    st.page_link("legacy_streamlit/pages/05_Diagnostico_Financeiro.py", label="Diagnóstico", icon="✨")
    st.page_link("legacy_streamlit/pages/18_Investidor_Dashboard.py", label="Score Financeiro", icon="📌")
    if mode == "Admin":
        st.markdown("**ADMIN**")
        st.page_link("legacy_streamlit/pages/17_Machine_Learning.py", label="Machine Learning", icon="🧠")
        st.page_link("legacy_streamlit/pages/12_Jobs_e_Execucoes.py", label="Jobs", icon="⚙️")
        st.page_link("legacy_streamlit/pages/13_Orquestrador_Geral.py", label="Orquestrador", icon="🚀")
        st.page_link("legacy_streamlit/pages/22_Producao_Healthcheck.py", label="Healthcheck", icon="🛡️")
        st.page_link("legacy_streamlit/pages/98_API_Keys.py", label="API Keys", icon="🔑")
        st.page_link("legacy_streamlit/pages/99_Planos.py", label="Planos", icon="💎")

render_hero(
    "ERP financeiro inteligente para gastos, orçamento e investimentos",
    "Conecte receitas, despesas, contas, cartões, metas, carteira, alertas e inteligência financeira em um único produto SaaS de apoio à decisão.",
    eyebrow="FinanceOS · SaaS financeiro",
    status="Controle financeiro + investimentos + IA aplicada, sem vender recomendação financeira",
    metrics={"Camadas": "ERP · Investimentos · Inteligência", "Modo": "Demo" if DEV_MODE else ENV, "Produto": "SaaS ready"},
)

c1, c2, c3, c4 = st.columns(4)
with c1: render_metric_card("Saldo mensal", "A configurar", "Receitas - despesas", "blue")
with c2: render_metric_card("% investido", "A configurar", "Conectado ao orçamento", "green")
with c3: render_metric_card("Score financeiro", "Em preparação", "Base para IA", "purple")
with c4: render_metric_card("Alertas", "0 ativos", "Sem dados ainda", "yellow")

render_section_header("Fluxo ideal do cliente", "Uma experiência simples para o usuário final, mantendo ML, backtests e jobs nos bastidores.")
cols = st.columns(3)
steps = [
    ("1. Organizar", "Cadastrar receitas, despesas, cartões, contas, categorias e recorrências."),
    ("2. Planejar", "Escolher modelos 50/30/20, 70/20/10, 60/30/10, base zero ou personalizado."),
    ("3. Decidir", "Ver oportunidades, carteira, alertas e sugestões financeiras com linguagem simples."),
]
for col, (title, desc) in zip(cols, steps):
    with col:
        render_callout(title, desc, kind="info")

render_section_header("Comece pela camada financeira")
left, right = st.columns([1.1, .9])
with left:
    st.page_link("legacy_streamlit/pages/03_Despesas.py", label="Cadastrar despesas", icon="💳")
    st.page_link("legacy_streamlit/pages/04_Orcamento.py", label="Criar orçamento", icon="📊")
    st.page_link("legacy_streamlit/pages/20_Minha_Carteira.py", label="Conectar investimentos", icon="💼")
with right:
    render_empty_state(
        "Dados reais ainda não carregados",
        "Cadastre despesas e receitas para ativar diagnóstico, alertas de excesso, orçamento vs. realizado e sobra potencial para investir.",
        action_label="Abrir despesas",
        page="legacy_streamlit/pages/03_Despesas.py",
    )

st.caption("Aviso legal: o FinanceOS é uma plataforma analítica, educacional e de apoio à decisão. Não é recomendação financeira, consultoria de valores mobiliários ou promessa de rentabilidade.")
