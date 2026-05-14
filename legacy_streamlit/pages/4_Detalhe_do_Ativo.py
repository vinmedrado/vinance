from db import pg_compat as dbcompat
from pathlib import Path
import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
DB = Path(__file__).resolve().parents[1] / "data" / "POSTGRES_RUNTIME_DISABLED"
st.set_page_config(page_title="FinanceOS · Ativo", layout="wide")
st.title("Detalhe do Ativo")
with dbcompat.connect(DB) as c:
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "assets" not in tables:
        st.warning("Tabela assets não encontrada.")
        st.stop()
    tickers = [r[0] for r in c.execute("SELECT ticker FROM assets WHERE ticker IS NOT NULL ORDER BY ticker LIMIT 2000").fetchall()]
    ticker = st.selectbox("Ticker", tickers) if tickers else st.text_input("Ticker")
    if not ticker:
        st.stop()
    asset = pd.read_sql_query("SELECT * FROM assets WHERE ticker=? LIMIT 1", c, params=[ticker])
    st.subheader("Cadastro")
    st.dataframe(asset, use_container_width=True)
    if "asset_prices" in tables and not asset.empty:
        price_cols = [r[1] for r in c.execute("PRAGMA table_info(asset_prices)").fetchall()]
        if "asset_id" in price_cols and "close" in price_cols and "date" in price_cols:
            asset_id = int(asset.iloc[0]["id"])
            prices = pd.read_sql_query("SELECT date, close FROM asset_prices WHERE asset_id=? ORDER BY date", c, params=[asset_id])
            st.subheader("Histórico de preço")
            if prices.empty: st.info("Sem preços.")
            else: st.line_chart(prices.set_index("date"))
    if "asset_scores" in tables:
        st.subheader("Score")
        scores = pd.read_sql_query("SELECT * FROM asset_scores WHERE ticker=? ORDER BY rowid DESC LIMIT 5", c, params=[ticker])
        st.dataframe(scores, use_container_width=True)
