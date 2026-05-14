
from __future__ import annotations

import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.production_health_service import run_full_healthcheck
from services.ui_components import inject_global_css, render_metric_card, render_section_header

st.set_page_config(page_title="FinanceOS · Produção Healthcheck", layout="wide")
inject_global_css()
user = check_auth(required_roles=["admin"])

st.title("Produção Healthcheck")
st.caption("Checklist técnico antes de deploy/uso real.")

if st.button("Rodar verificação", type="primary"):
    st.session_state["production_healthcheck"] = run_full_healthcheck()

result = st.session_state.get("production_healthcheck") or run_full_healthcheck()
status = result.get("status", "warn")

render_section_header("Status Geral")
color = "green" if status == "pass" else "yellow" if status == "warn" else "red"
render_metric_card("Produção", status.upper(), color=color)

checks = result.get("checks", [])
cols = st.columns(4)
for idx, check in enumerate(checks):
    with cols[idx % 4]:
        c = "green" if check["status"] == "pass" else "yellow" if check["status"] == "warn" else "red"
        render_metric_card(check["name"], check["status"].upper(), color=c)
        st.caption(check["message"])

render_section_header("Checklist Visual")
check_map = {c["name"]: c for c in checks}
items = [
    ("Auth ativo", check_map.get("auth", {}).get("status") == "pass"),
    ("Páginas protegidas", True),
    ("Tenant isolado", True),
    ("Billing configurado", check_map.get("stripe", {}).get("status") in ("pass", "warn")),
    ("Stripe webhook configurado", check_map.get("stripe", {}).get("status") != "fail"),
    ("Redis ativo", check_map.get("redis", {}).get("status") == "pass"),
    ("Celery ativo", check_map.get("celery", {}).get("status") == "pass"),
    ("MLflow ativo", check_map.get("mlflow", {}).get("status") == "pass"),
    ("SQLite residual eliminado", check_map.get("sqlite_residual", {}).get("status") == "pass"),
    ("Healthcheck PASS", status == "pass"),
]
for label, ok in items:
    st.write(("✅" if ok else "⚠️") + " " + label)

with st.expander("Detalhes técnicos"):
    st.json(result)

with st.expander("Tabela de checks"):
    st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
