# Vinance — Enterprise Backend Final Patch

## Escopo aplicado

Patch incremental focado em backend enterprise multi-tenant, sem recriar projeto, sem alterar branding/logo e sem mexer no frontend visual.

## Principais entregas

- Fundação multi-tenant com `organizations`, `organization_members`, `tenant_settings` e `subscriptions`.
- RBAC com roles enterprise e `require_permission("permission")`.
- Auth hardening com refresh token rotation e armazenamento de hash de tokens.
- Tabelas para sessões, refresh tokens, reset de senha e verificação de email.
- Audit logs por organização.
- Billing organization-level com planos `free`, `pro`, `premium`, `enterprise`.
- Serviço central `backend/app/services/plan_limits_service.py`.
- Migration incremental `20260508_0009_enterprise_multi_tenant.py`.
- `organization_id`, `created_by`, `updated_by`, `deleted_at` preparados nas principais tabelas financeiras.
- Rotas ERP principais adaptadas para isolamento por organização.
- Healthchecks: `/health`, `/ready`, `/live`, `/metrics`.
- Middleware reforçado com rate limit, request id, payload limit e secure headers.
- CI GitHub Actions criado.
- Documentação enterprise em `docs/`.
- Smoke tests mínimos criados em `tests/`.

## Validação executada neste ambiente

- `python -m compileall backend tests`: OK
- `pytest -q tests`: OK — 8 passed, 1 skipped
- `npm run build`: não validado completamente porque o ambiente não tinha dependências do frontend instaladas (`react/jsx-runtime`, `axios` etc.). O patch não alterou frontend/branding.
- `docker compose config`: não executado porque Docker não está disponível neste ambiente.
- `alembic upgrade head`: não executado porque SQLAlchemy/Alembic não estão instalados no runtime do container atual, mas a migration foi criada e o backend compila.

## Limitações restantes

- Rodar `pip install -r requirements.txt` antes de `alembic upgrade head` e `pytest` em ambiente real.
- Rodar `npm install && npm run build` dentro de `frontend/` em ambiente Node completo.
- Validar migrations contra PostgreSQL real.
- Ajustar permissões em 100% das rotas legadas de investimento/backtest caso elas sejam expostas para múltiplos clientes no mesmo deploy.
