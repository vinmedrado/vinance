import pandas as pd
import streamlit as st

from services.ui_helpers import format_percent, safe_query

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
st.set_page_config(page_title="FinanceOS · Cobertura de Dados", layout="wide")
st.title("Cobertura de Dados")
st.caption("Verifique quais ativos possuem histórico de preços carregado no banco.")

st.info("Para atualizar dados de mercado sem terminal, acesse a página: Automação de Dados de Mercado.")
try:
    st.page_link("legacy_streamlit/pages/11_Automacao_Dados_Mercado.py", label="Atualizar Dados de Mercado", icon="🔄")
except Exception:
    st.button("Atualizar Dados de Mercado", disabled=True, help="Abra a página legacy_streamlit/pages/11_Automacao_Dados_Mercado.py no menu lateral.")

coverage = safe_query("""
SELECT
    a.ticker,
    a.name,
    COALESCE(a.asset_class, 'unknown') AS asset_class,
    MIN(p.date) AS data_inicial,
    MAX(p.date) AS data_final,
    COUNT(p.id) AS total_registros,
    CASE WHEN COUNT(p.id) > 0 THEN 'OK' ELSE 'SEM DADOS' END AS status
FROM assets a
LEFT JOIN asset_prices p ON p.asset_id = a.id
GROUP BY a.id, a.ticker, a.name, a.asset_class
ORDER BY a.asset_class, a.ticker
""")

if coverage.empty:
    st.warning("Nenhum ativo encontrado ou tabelas ausentes.")
    st.stop()

with_data = int((coverage["total_registros"] > 0).sum())
without_data = int((coverage["total_registros"] <= 0).sum())
total = len(coverage)
pct = with_data / total if total else 0

c1, c2, c3 = st.columns(3)
c1.metric("Ativos com dados", with_data)
c2.metric("Ativos sem dados", without_data)
c3.metric("Cobertura", format_percent(pct))

st.divider()
f1, f2, f3 = st.columns(3)
classes = ["Todos"] + sorted([x for x in coverage["asset_class"].dropna().unique().tolist()])
selected_class = f1.selectbox("Classe", classes)
selected_status = f2.selectbox("Status", ["Todos", "OK", "SEM DADOS"])
search = f3.text_input("Buscar ticker/nome", "")

filtered = coverage.copy()
if selected_class != "Todos":
    filtered = filtered[filtered["asset_class"] == selected_class]
if selected_status != "Todos":
    filtered = filtered[filtered["status"] == selected_status]
if search.strip():
    q = search.strip().upper()
    filtered = filtered[
        filtered["ticker"].astype(str).str.upper().str.contains(q, na=False)
        | filtered["name"].astype(str).str.upper().str.contains(q, na=False)
    ]

st.dataframe(filtered, use_container_width=True, hide_index=True)
