from __future__ import annotations
import os
import streamlit as st
from services.i18n_service import language_selector
from services.ui_components import inject_global_css, render_hero
from services.auth_middleware import is_production

st.set_page_config(page_title="FinanceOS · Registro", layout="centered")
inject_global_css()
language_selector()
render_hero("Criar conta", "Comece pelo controle financeiro e evolua para inteligência de investimentos.", eyebrow="Onboarding")
with st.container(border=True):
    name = st.text_input("Nome")
    email = st.text_input("Email")
    password = st.text_input("Senha", type="password")
    if st.button("Começar grátis", type="primary", use_container_width=True):
        if is_production():
            st.error("Registro em produção deve usar backend/JWT e política de senha.")
        else:
            st.session_state["user"] = {"id":"local-user", "tenant_id":"local-tenant", "email":email or "demo@financeos.local", "full_name":name, "role":"investor", "plan":"free", "preferred_currency":"BRL"}
            st.switch_page("legacy_streamlit/pages/01_Onboarding.py")
