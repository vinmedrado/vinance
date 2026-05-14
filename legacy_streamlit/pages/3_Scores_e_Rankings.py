from db import pg_compat as dbcompat
from pathlib import Path
import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
DB = Path(__file__).resolve().parents[1] / "data" / "POSTGRES_RUNTIME_DISABLED"
st.set_page_config(page_title="FinanceOS · Scores", layout="wide")
st.title("Scores e Rankings")
with dbcompat.connect(DB) as c:
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "asset_scores" not in tables:
        st.info("Nenhum score calculado ainda.")
        st.stop()
    cols = [r[1] for r in c.execute("PRAGMA table_info(asset_scores)").fetchall()]
    asset_class = st.sidebar.selectbox("Classe", ["all"] + sorted([x[0] for x in c.execute("SELECT DISTINCT asset_class FROM asset_scores WHERE asset_class IS NOT NULL").fetchall()]) if "asset_class" in cols else ["all"])
    sql = "SELECT * FROM asset_scores WHERE 1=1"
    params=[]
    if asset_class != "all" and "asset_class" in cols:
        sql += " AND asset_class=?"; params.append(asset_class)
    order = "score_total" if "score_total" in cols else "rowid"
    df = pd.read_sql_query(sql + f" ORDER BY {order} DESC LIMIT 500", c, params=params)
    if df.empty:
        st.info("Nenhum score para os filtros.")
    else:
        st.dataframe(df, use_container_width=True)
