from __future__ import annotations
import streamlit as st
from services.auth_middleware import check_auth
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout

st.set_page_config(page_title="FinanceOS · Alertas", layout="wide")
inject_global_css(); check_auth()
render_hero("Meus alertas", "Configure lembretes simples para oportunidades, carteira, orçamento e excesso de gastos.", eyebrow="Alertas inteligentes", status="Email/webhook podem ser conectados em produção")
c1,c2,c3=st.columns(3)
with c1: render_metric_card("Alertas ativos", 0, color="blue")
with c2: render_metric_card("Pendentes", 0, color="yellow")
with c3: render_metric_card("Críticos", 0, color="red")
render_section_header("Criar alerta")
kind=st.selectbox("Tipo", ["Gasto acima do orçamento", "Oportunidade de ativo", "Mudança de classificação", "Meta mensal de investimento", "Preço alvo"])
name=st.text_input("Nome/ativo/categoria", placeholder="Ex.: Alimentação, PETR4, Meta reserva")
operator=st.selectbox("Condição", [">=", "<=", "=="])
value=st.number_input("Valor", value=70.0)
channel=st.multiselect("Canal", ["Tela", "Email", "Webhook"], default=["Tela"])
if st.button("Criar alerta", type="primary"):
    if not name: st.warning("Informe o nome, ativo ou categoria.")
    else: st.success("Alerta validado no fluxo demo. Persistência real deve usar PostgreSQL.")
render_empty_state("Sem alertas ativos", "Crie alertas para orçamento, oportunidades, carteira e metas. O usuário final não precisa ver logs técnicos.")
