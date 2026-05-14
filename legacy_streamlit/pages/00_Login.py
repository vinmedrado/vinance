from __future__ import annotations

import os
import streamlit as st
from services.i18n_service import language_selector
from services.ui_components import inject_global_css, render_hero, render_callout
from services.auth_middleware import is_dev_mode, is_production

st.set_page_config(page_title="FinanceOS · Login", layout="centered")
inject_global_css()
language_selector()

render_hero(
    "Entrar no FinanceOS",
    "ERP financeiro inteligente para controlar gastos, orçamento, investimentos e alertas em uma experiência única.",
    eyebrow="Acesso seguro",
    status="Modo produção exige autenticação real via backend/JWT",
)

if is_dev_mode():
    render_callout("Modo Demo ativo", "Disponível apenas em desenvolvimento local. Em produção, usuário fake é bloqueado.", "warning")

with st.container(border=True):
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    if st.button("Entrar", type="primary", use_container_width=True):
        if is_production():
            st.error("Login real via backend/JWT deve ser configurado para produção.")
        else:
            st.session_state["user"] = {
                "id": "local-user",
                "tenant_id": "local-tenant",
                "email": email or "demo@financeos.local",
                "role": "admin",
                "plan": "enterprise",
                "preferred_language": st.session_state.get("lang", "pt_BR"),
                "preferred_currency": "BRL",
            }
            st.success("Login local realizado.")
            st.switch_page("legacy_streamlit/main_streamlit.py")
    if is_dev_mode() and st.button("Entrar demo", use_container_width=True):
        st.session_state["user"] = {"id":"demo-user", "tenant_id":"demo-tenant", "email":"demo@financeos.local", "role":"investor", "plan":"free", "preferred_currency":"BRL"}
        st.switch_page("legacy_streamlit/main_streamlit.py")
st.page_link("legacy_streamlit/pages/00_Register.py", label="Criar conta")
