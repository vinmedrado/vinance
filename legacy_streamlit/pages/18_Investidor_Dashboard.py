from __future__ import annotations
import streamlit as st
from services.auth_middleware import check_auth
from services.erp_finance_service import summarize_expenses, money
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_callout, render_empty_state

st.set_page_config(page_title="FinanceOS · Dashboard", layout="wide")
inject_global_css(); user=check_auth()
summary=summarize_expenses(); income=6500.0; sobra=income-summary['total']; pct=(summary['invested']/income*100) if income else 0
render_hero("Dashboard do cliente", "Uma visão simples do dinheiro: gastos, sobra para investir, oportunidades e alertas sem termos técnicos.", eyebrow="Cliente/Investidor", status="Controle financeiro + investimentos + inteligência")
c1,c2,c3,c4=st.columns(4)
with c1: render_metric_card("Gastos do mês", money(summary['total']), "Despesas registradas", "red")
with c2: render_metric_card("Sobra estimada", money(sobra), "Potencial para metas/investir", "green" if sobra>=0 else "red")
with c3: render_metric_card("Investido no mês", f"{pct:.1f}%", "Comparado à renda", "blue")
with c4: render_metric_card("Risco financeiro", "Moderado", "Baseado no fluxo mensal", "yellow")
render_section_header("O que o FinanceOS entendeu")
a,b,c=st.columns(3)
with a: render_callout("Oportunidade", "Você já separou uma parte do mês para investimentos/reserva. A próxima melhoria é manter consistência.", "success")
with b: render_callout("Atenção", "Pendências e recorrências devem ser revisadas antes do fechamento mensal.", "warning")
with c: render_callout("Próximo passo", "Escolha um modelo de orçamento e conecte as despesas reais ao planejado.", "info")
render_section_header("Atalhos")
st.page_link("legacy_streamlit/pages/03_Despesas.py", label="Gerenciar despesas", icon="💳")
st.page_link("legacy_streamlit/pages/04_Orcamento.py", label="Ver orçamento", icon="📊")
st.page_link("legacy_streamlit/pages/19_Oportunidades_Mercado.py", label="Ver oportunidades", icon="📈")
st.caption("Aviso legal: plataforma analítica e educacional. Não é recomendação financeira.")
