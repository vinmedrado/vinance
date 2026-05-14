from __future__ import annotations

from datetime import date
import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
from services.financial_crud_service import create_transaction, list_transactions, money, month_ref, seed_demo_if_empty, summarize_month
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout

st.set_page_config(page_title="FinanceOS · Receitas", layout="wide")
inject_global_css()
check_auth()
try:
    seed_demo_if_empty()
except Exception:
    render_callout("Banco indisponível", "Configure o banco para cadastrar receitas reais.", "warning")
    st.stop()

render_hero("Receitas", "Cadastre entradas recorrentes ou avulsas e use a renda como base do orçamento e dos investimentos.", eyebrow="ERP Financeiro")
with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        valor = st.number_input("Valor", min_value=0.0, step=100.0)
        descricao = st.text_input("Descrição", placeholder="Salário, freela, venda...")
    with c2:
        data_lanc = st.date_input("Data", value=date.today())
        recorrencia = st.selectbox("Recorrência", ["Única", "Mensal", "Semanal", "Anual"])
    with c3:
        conta = st.text_input("Conta", value="Conta principal")
        status = st.selectbox("Status", ["Recebido", "Pendente"])
    if st.button("Salvar receita", type="primary"):
        try:
            create_transaction({"transaction_type":"income", "amount":valor, "description":descricao, "category":"Receitas", "transaction_date":data_lanc, "recurrence":recorrencia, "account_name":conta, "status":status, "payment_method":"Transferência"})
            st.success("Receita salva no banco.")
            st.rerun()
        except Exception as exc:
            st.warning(str(exc))

selected_month = st.text_input("Mês", value=month_ref())
summary = summarize_month(month=selected_month)
c1,c2,c3 = st.columns(3)
with c1: render_metric_card("Receitas do mês", money(summary['income']), color="green")
with c2: render_metric_card("Sobra disponível", money(summary['available_to_invest']), color="blue")
with c3: render_metric_card("Meta de investimento", money(summary['recommended_investment']), color="purple")
rows = list_transactions(transaction_type="income", month=selected_month)
render_section_header("Receitas cadastradas")
if rows:
    df = pd.DataFrame(rows)
    view = df[["id","transaction_date","description","amount","account_name","status","recurrence"]].copy()
    view.columns = ["ID","Data","Descrição","Valor","Conta","Status","Recorrência"]
    view["Valor"] = view["Valor"].map(money)
    st.dataframe(view, hide_index=True, use_container_width=True)
else:
    render_empty_state("Nenhuma receita cadastrada", "Cadastre sua renda para ativar orçamento e diagnóstico.")
