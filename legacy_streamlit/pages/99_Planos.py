from __future__ import annotations
import os
import streamlit as st
from services.auth_middleware import check_auth
from services.ui_components import inject_global_css, render_hero, render_callout

st.set_page_config(page_title="FinanceOS · Planos", layout="wide")
inject_global_css(); check_auth()
render_hero("Planos FinanceOS", "Monetização clara para um ERP financeiro inteligente com investimentos e IA.", eyebrow="SaaS monetization", status="Stripe preservado como integração opcional")
plans=[
    ("Free","R$ 0",["Carteira básica","Poucas oportunidades","Limite de ativos","Sem alertas avançados"],"Começar grátis"),
    ("Pro","R$ 49/mês",["Oportunidades por ML","Alertas","Carteira completa","Ranking multi-mercado","Backtests limitados"],"Assinar Pro"),
    ("Premium/Enterprise","R$ 199+/mês",["Automações","API","Relatórios","Multiusuário","Suporte","White-label futuro"],"Falar com vendas"),
]
cols=st.columns(3)
for col,(name,price,items,cta) in zip(cols,plans):
    with col:
        with st.container(border=True):
            st.subheader(name); st.metric("Preço", price)
            for it in items: st.write(f"✓ {it}")
            if st.button(cta, key=name, use_container_width=True): st.info("Configure STRIPE_SECRET_KEY para checkout real. Integração backend não foi removida.")
stripe_ok=bool(os.getenv('STRIPE_SECRET_KEY'))
render_callout("Status Stripe", "Configurado" if stripe_ok else "Stripe ainda não configurado. A página mostra CTAs sem quebrar a integração existente.", "success" if stripe_ok else "warning")
st.caption("Aviso legal: o FinanceOS é plataforma analítica e educacional. Não é recomendação financeira.")
