# FinanceOS — PATCH 48.1 HARDENING VALIDADO

Aplicado sobre `FinanceOS_PATCH_48_HARDENING.zip`, seguindo o PDF `FinanceOS ANALISE PATCH39 47(2).pdf`.

## Correções consolidadas

1. `auth_middleware.py`
   - Remove fallback admin em produção.
   - Dev admin só com `FINANCEOS_DEV_MODE=true`.

2. Páginas Streamlit
   - `check_auth()` aplicado em todas as páginas relevantes.
   - Roles por escopo:
     - investidor/autenticado
     - analyst/admin
     - admin

3. `plan_guard.py`
   - `get_tenant_plan()` consulta `tenants.plan`.
   - Fallback seguro para `free`.

4. Auth API
   - Refresh token recria access token com `role` e `plan`.
   - Logout grava token em blacklist Redis.
   - Middleware FastAPI checa blacklist.

5. Stripe Billing
   - Webhook `checkout.session.completed` atualiza `tenants` e `users`.
   - Webhook `customer.subscription.deleted` rebaixa para `free`.

6. Docker
   - `env_file` uniformizado para `.env`.
   - `.env` criado/fortalecido.
   - `SECRET_KEY` gerado.
   - `FINANCEOS_DEV_MODE=false`.

7. Celery
   - `sync_all_prices()` chama `scripts/sync_historical_prices.py`.
   - `check_drift()` chama `ml_drift_service`.
   - `run_backtest_async()` tenta executar script de backtest real.

8. ML
   - `model_type=xgboost`.
   - `model_type=lightgbm`.
   - MLflow tracking integrado ao treino.

9. Currency
   - Conversão real via Frankfurter API.
   - Cache Redis de 1 hora.

10. MLflow
   - Backend store em PostgreSQL `financeos_mlflow`.
   - Script de init cria bancos `financeos` e `financeos_mlflow`.

## Validação
Todos os arquivos Python principais compilaram sem erro no empacotamento.
