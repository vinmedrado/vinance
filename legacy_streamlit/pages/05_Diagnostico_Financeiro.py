from __future__ import annotations

import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import money, month_ref, seed_demo_if_empty
from services.financial_intelligence_service import build_financial_diagnosis
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_callout, render_empty_state

st.set_page_config(page_title="FinanceOS · Diagnóstico Financeiro", layout="wide")
inject_global_css()
check_auth()

try:
    seed_demo_if_empty()
except Exception:
    render_callout("Diagnóstico indisponível", "Configure o banco para carregar dados financeiros reais.", "warning")
    st.stop()

render_hero(
    "Diagnóstico financeiro inteligente",
    "Entenda score, alertas, previsão de fechamento, oportunidades de economia e conexão com investimento sem termos técnicos.",
    eyebrow="Inteligência Financeira",
    status="IA aplicada ao ERP financeiro · linguagem simples para cliente final",
)

selected_month = st.text_input("Mês de referência", value=month_ref())
d = build_financial_diagnosis(month=selected_month)
summary = d["summary"]

c1, c2, c3, c4 = st.columns(4)
with c1: render_metric_card("Score financeiro", f"{d['score']}/100", d['label'], "green" if d['score'] >= 70 else "yellow" if d['score'] >= 50 else "red")
with c2: render_metric_card("Saldo previsto", money(d['forecast']['projected_balance']), "Fechamento estimado", "blue")
with c3: render_metric_card("Investimento sugerido", money(d['investment']['suggested']), "Com base na sobra", "purple")
with c4: render_metric_card("Categorias acima", len(d['above_limits']), "Limites do orçamento", "red" if d['above_limits'] else "green")

render_section_header("Principais alertas")
cols = st.columns(3)
for idx, alert in enumerate(d["alerts"]):
    with cols[idx % 3]:
        render_callout("Alerta financeiro", alert, "warning" if "Nenhum" not in alert else "success")

render_section_header("Recomendações")
cols = st.columns(2)
items = d["savings_suggestions"] + [d["investment"]["message"], d["forecast"]["message"]]
for idx, item in enumerate(items):
    with cols[idx % 2]:
        render_callout("Próximo passo", item, "info")

render_section_header("Orçamento conectado aos investimentos")
if not d["budget_rows"]:
    render_empty_state("Sem orçamento ativo", "Escolha um modelo de orçamento para ativar comparação planejado vs. realizado.", "Abrir orçamento", "legacy_streamlit/pages/04_Orcamento.py")
else:
    df = pd.DataFrame(d["budget_rows"])
    view = df.copy()
    view["Percentual"] = view["Percentual"].map(lambda v: f"{float(v):.0%}")
    for col in ["Planejado", "Realizado", "Diferença"]:
        view[col] = view[col].map(money)
    st.dataframe(view, use_container_width=True, hide_index=True)

st.caption("Diagnóstico educacional e analítico. Não representa recomendação financeira ou promessa de resultado.")
