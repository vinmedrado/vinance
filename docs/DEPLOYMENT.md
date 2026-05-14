# Deployment

## Docker Compose

```bash
docker compose up --build
```

Serviços:

- `frontend`: React/Vite servido por Nginx em `localhost:3000`.
- `backend`: FastAPI em `localhost:8000`.
- `postgres`: banco principal.
- `redis`: filas/cache.
- `mlflow`: tracking de modelos.
- `worker` e `beat`: jobs.
- `admin_streamlit`: perfil opcional para legado/admin.

## Produção

- Use PostgreSQL real.
- Configure `FINANCEOS_ENV=production`.
- Não use SQLite em produção.
- Configure CORS apenas com domínios finais.
- Configure Stripe, Redis e MLflow conforme ambiente.

---

## Ultra Premium UX Patch

O frontend oficial do FinanceOS é React/Vite com TypeScript. Este patch adicionou uma camada de design system premium, componentes reutilizáveis, dark mode refinado, responsividade, lazy loading e melhorias visuais nas telas principais do ERP financeiro.

Telas refinadas:
- Login
- Onboarding
- Dashboard Financeiro
- Despesas
- Orçamento
- Metas/CRUDs financeiros
- Diagnóstico Financeiro
- Investimentos/Carteira/Alertas
- Planos
- Landing page

Comandos principais:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Backend:

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker compose up --build
```
