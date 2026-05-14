# Billing e Plan Limits

Planos:

- free
- pro
- premium
- enterprise

Billing é organization-level via `organizations` e `subscriptions`. Limites são centralizados em `backend/app/services/plan_limits_service.py` e aplicados em criação de despesas, contas, usuários, metas e base pronta para jobs/backtests/exportações.

Quando um limite é atingido, a API retorna payload com `Plan limit reached` e `upgrade_required=true`.
