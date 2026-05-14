# Admin Streamlit legado

O frontend oficial do FinanceOS agora é React em `frontend/` e abre em `http://localhost:3000`.

O Streamlit foi mantido apenas como console interno/admin legado para telas operacionais históricas, ML, jobs, backtests e diagnóstico técnico.

Para abrir opcionalmente:

```bash
streamlit run legacy_streamlit/app.py
# ou
 docker compose --profile admin up admin_streamlit
```
