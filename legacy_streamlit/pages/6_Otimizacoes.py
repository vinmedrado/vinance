from db import pg_compat as dbcompat
from pathlib import Path
import pandas as pd
import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['analyst', 'admin'])
DB = Path(__file__).resolve().parents[1] / "data" / "POSTGRES_RUNTIME_DISABLED"
st.set_page_config(page_title="FinanceOS · Otimizações", layout="wide")
st.title("Otimizações")
with dbcompat.connect(DB) as c:
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "optimization_runs" not in tables:
        st.info("Nenhuma otimização criada ainda.")
        st.stop()
    runs = pd.read_sql_query("SELECT * FROM optimization_runs ORDER BY id DESC", c)
    st.subheader("Runs")
    st.dataframe(runs, use_container_width=True)
    if "optimization_results" in tables:
        st.subheader("Melhores resultados")
        cols = [r[1] for r in c.execute("PRAGMA table_info(optimization_results)").fetchall()]
        order = "score_robustez" if "score_robustez" in cols else "sharpe_ratio" if "sharpe_ratio" in cols else "rowid"
        results = pd.read_sql_query(f"SELECT * FROM optimization_results ORDER BY {order} DESC LIMIT 100", c)
        st.dataframe(results, use_container_width=True)
