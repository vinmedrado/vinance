# FinanceOS — PATCH 39–47 Evolução Internacional

Aplicado sobre PATCH 38 conforme PDF anexado.

## Implementado

### PATCH 39 — PostgreSQL + Alembic
- db/database.py com SQLAlchemy async/sync
- Alembic configurado para PostgreSQL
- Migration `0039_0047_international_saas.py`
- docker-compose com Postgres 16, Redis 7, MLflow, worker e beat
- requirements com asyncpg, psycopg2, celery, auth, billing, ML lifecycle

### PATCH 40 — Auth JWT + RBAC
- backend/app/auth/
- JWT access/refresh
- bcrypt/passlib
- FastAPI auth router
- services/auth_middleware.py
- páginas 00_Login.py e 00_Register.py
- estrutura users/tenants na migration

### PATCH 41 — i18n + multimercado
- locales/pt_BR.json
- locales/en_US.json
- locales/es_ES.json
- services/i18n_service.py
- services/currency_service.py
- catalog_fallback internacional:
  - us_equities.csv
  - us_etfs.csv
  - global_indices.csv
  - forex_pairs.csv
  - us_reits.csv

### PATCH 42 — Monetização SaaS
- subscription_plans na migration
- backend/app/billing/stripe_router.py
- services/plan_guard.py
- pages/99_Planos.py
- pages/98_API_Keys.py
- api_keys na migration

### PATCH 43 — Portfólio real + P&L
- services/portfolio_service.py
- portfolio_accounts
- portfolio_transactions
- portfolio_snapshots
- pages/20_Minha_Carteira.py
- investor_overview integrado ao patrimônio real quando houver transações

### PATCH 44 — ML lifecycle
- requirements com xgboost, lightgbm, mlflow, shap, optuna, scipy
- services/ml_drift_service.py
- scripts/ml_retrain_schedule.py
- mlflow service no docker-compose
- ml_drift_reports na migration

### PATCH 45 — Redis + Celery
- workers/celery_app.py
- workers/tasks.py
- Redis service no docker-compose
- worker/beat no docker-compose

### PATCH 46 — Alertas inteligentes
- user_alerts na migration
- services/alert_engine.py
- pages/21_Meus_Alertas.py
- task send_alert_email no Celery

### PATCH 47 — Landing + Onboarding
- frontend/landing/index.html
- pages/01_Onboarding.py

## Importante
Esta entrega cria a fundação internacional e mantém compatibilidade com o app Streamlit antigo.
Algumas integrações externas exigem credenciais reais:
- Stripe
- SendGrid
- provedores de dados pagos
- DATABASE_URL PostgreSQL real em produção

## Execução local
```bash
docker-compose up --build
```

Ou modo legado:
```bash
streamlit run legacy_streamlit/app.py
```

## Migração
```bash
alembic upgrade head
```
