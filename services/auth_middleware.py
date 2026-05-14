from __future__ import annotations

import os
import streamlit as st

ROLE_PAGES = {
    "investor": ["02_Financeiro_Visao_Geral.py", "03_Despesas.py", "04_Orcamento.py", "18_Investidor_Dashboard.py", "19_Oportunidades_Mercado.py", "20_Minha_Carteira.py", "21_Meus_Alertas.py"],
    "analyst": ["17_Machine_Learning.py", "18_Investidor_Dashboard.py", "19_Oportunidades_Mercado.py", "20_Minha_Carteira.py"],
    "admin": ["*"],
}


def is_production() -> bool:
    return os.getenv("FINANCEOS_ENV", "development").lower() == "production"


def is_dev_mode() -> bool:
    return os.getenv("FINANCEOS_DEV_MODE", "false").lower() == "true" and not is_production()


def _dev_user(role: str = "admin") -> dict:
    return {
        "id": "demo-user",
        "tenant_id": "demo-tenant",
        "email": "demo@financeos.local",
        "role": role,
        "plan": "enterprise" if role == "admin" else "free",
        "preferred_language": st.session_state.get("lang", "pt_BR"),
        "preferred_currency": st.session_state.get("currency", "BRL"),
    }


def check_auth(required_roles: list[str] | None = None):
    if "user" not in st.session_state:
        if is_dev_mode():
            st.session_state["user"] = _dev_user("admin")
            st.caption("Modo Demo: usuário local criado apenas para desenvolvimento.")
        else:
            st.warning("Sessão não encontrada. Faça login para continuar.")
            st.switch_page("pages/00_Login.py")
            st.stop()

    user = st.session_state["user"]
    if is_production() and user.get("email", "").endswith("@financeos.local"):
        st.error("Usuário demo bloqueado em produção. Faça login com autenticação real.")
        st.switch_page("pages/00_Login.py")
        st.stop()

    if required_roles and user.get("role") not in required_roles:
        st.error("Você não tem permissão para esta página.")
        st.stop()

    st.session_state["tenant_id"] = user.get("tenant_id")
    return user
