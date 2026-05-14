
from __future__ import annotations
import secrets, hashlib
import streamlit as st

from services.auth_middleware import check_auth
user = check_auth(required_roles=['admin'])
st.set_page_config(page_title="FinanceOS · API Keys", layout="wide")
st.title("API Keys")
if user.get("plan") not in ("pro", "enterprise"):
    st.warning("API Keys disponíveis no plano Pro+.")
    st.stop()
name = st.text_input("Nome da chave")
if st.button("Gerar API Key"):
    raw = "fos_live_" + secrets.token_urlsafe(32)
    st.success("Copie agora. A chave não será exibida novamente.")
    st.code(raw)
    st.caption("Hash para persistir no banco: " + hashlib.sha256(raw.encode()).hexdigest())
