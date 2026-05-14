# Legacy Streamlit Admin

Este diretório preserva a interface Streamlit histórica do FinanceOS apenas como console legado/admin interno.

O frontend oficial do produto SaaS é o React/Vite em `frontend/`.

Uso opcional local:

```bash
streamlit run legacy_streamlit/app.py
```

Uso opcional via Docker Compose local:

```bash
docker compose --profile admin up admin_streamlit
```

Não use Streamlit como frontend principal em produção pública.
