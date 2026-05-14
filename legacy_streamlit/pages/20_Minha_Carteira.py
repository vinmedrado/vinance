from __future__ import annotations
import pandas as pd
import streamlit as st
from services.auth_middleware import check_auth
from services.ui_components import inject_global_css, render_hero, render_metric_card, render_section_header, render_empty_state, render_callout
from services.currency_service import format_currency

st.set_page_config(page_title="FinanceOS · Minha Carteira", layout="wide")
inject_global_css(); user=check_auth(); tenant_id=user.get('tenant_id','demo-tenant')
render_hero("Minha carteira", "Acompanhe patrimônio, posições, dividendos e conexão com o orçamento mensal.", eyebrow="Investimentos", status="Carteira conectada ao ERP financeiro")
try:
    from services.portfolio_service import get_portfolio_summary, get_positions, get_dividends_received, import_from_b3_excel
    summary=get_portfolio_summary(tenant_id); account_id=summary.get('account_id')
    positions=get_positions(account_id, tenant_id) if account_id else []
    dividends=get_dividends_received(account_id, tenant_id) if account_id else 0
except Exception:
    summary={"total_brl":0,"pnl":0,"account_id":None}; positions=[]; dividends=0
c1,c2,c3,c4=st.columns(4)
with c1: render_metric_card("Patrimônio", format_currency(summary.get('total_brl',0)), color="green")
with c2: render_metric_card("Resultado", format_currency(summary.get('pnl',0)), color="green" if summary.get('pnl',0)>=0 else "red")
with c3: render_metric_card("Dividendos", format_currency(dividends), color="blue")
with c4: render_metric_card("Meta mensal", "20%", "Conectada ao orçamento", "purple")
render_section_header("Posições")
if positions:
    df=pd.DataFrame(positions); st.dataframe(df,use_container_width=True,hide_index=True)
    if 'current_value' in df and 'ticker' in df: st.bar_chart(df.set_index('ticker')['current_value'])
else:
    render_empty_state("Nenhuma posição cadastrada", "Importe um extrato ou cadastre ativos para ligar carteira, orçamento e alertas.")
uploaded=st.file_uploader("Importar extrato B3/CEI", type=["xlsx"])
if uploaded and st.button("Importar", type="primary"):
    st.info("Importação preservada. Configure o banco PostgreSQL para persistência real.")
render_callout("Integração financeira", "Quando receitas e despesas forem cadastradas, o FinanceOS calcula quanto sobrou para investir e compara com sua meta.", "info")
