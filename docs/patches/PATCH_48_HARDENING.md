# FinanceOS — PATCH 48 HARDENING

Aplicado sobre PATCH 39–47 conforme PDF de análise técnica.

## Fixes aplicados

### FIX 1 — auth_middleware sem fallback admin
- Removeu admin enterprise automático em produção.
- Dev mode só via `FINANCEOS_DEV_MODE=true`.

### FIX 2 — check_auth nas páginas
- Páginas originais e técnicas protegidas.
- Investidor aberto apenas para usuário autenticado.
- Admin/analyst aplicados conforme criticidade.

### FIX 3 — plan_guard consulta banco real
- `get_tenant_plan()` agora tenta consultar `tenants.plan`.
- Mantém fallback seguro para free.

### FIX 4 — refresh + logout real
- Refresh busca `role` e `plan` no banco.
- Logout grava token em blacklist Redis.
- `get_current_user()` verifica blacklist.

### FIX 5 — Stripe webhook persiste plano
- `checkout.session.completed` atualiza tenants/users.
- `customer.subscription.deleted` rebaixa tenant para free.

### FIX 6 — docker-compose env_file
- Uniformizado para `.env`.
- `.env` local criado a partir de `.env.example`.
- `FINANCEOS_DEV_MODE=false`.

### FIX 7 — Celery tasks reais
- `sync_all_prices()` chama script de preço.
- `check_drift()` chama drift service.
- `run_backtest_async()` tenta chamar script de backtest existente.

### FIX 8 — XGBoost + LightGBM + MLflow
- `model_type=xgboost`
- `model_type=lightgbm`
- MLflow tracking no treinamento.
- CLI aceita novos model types.

### FIX 9 — Currency converter real
- Frankfurter API.
- Cache Redis de 1 hora.

### FIX 10 — MLflow PostgreSQL
- MLflow usa PostgreSQL como backend store.
- Init script cria `financeos` e `financeos_mlflow`.

## Execução

```bash
docker-compose up --build
alembic upgrade head
streamlit run legacy_streamlit/app.py
```

## Observação
Este patch corrige os gaps críticos identificados no PDF e prepara o sistema para uso real controlado. Credenciais de Stripe, Redis, Postgres e SendGrid devem ser configuradas em `.env`.
