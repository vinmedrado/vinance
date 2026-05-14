# Vinance — Enterprise Backend V2

Este patch unifica a base enterprise do Vinance em torno de `organizations`, `users` e `organization_members`.

## Modelo oficial

- `organizations`: cliente/empresa/tenant oficial.
- `users`: identidade global do usuário.
- `organization_members`: vínculo do usuário com a organização, role e status.
- `roles`, `permissions`, `role_permissions`: matriz RBAC.
- `subscriptions`: billing por organização.
- `tenant_settings`: configurações por organização.
- `audit_logs`: trilha de auditoria por organização.

O modelo antigo `tenants` foi tratado como legado/compatibilidade. O auth novo não cria nem consulta `tenants` como fonte principal.

## Contexto autenticado

As dependencies oficiais são:

- `get_current_user()`
- `get_current_organization()`
- `get_organization_context()`
- `require_permission("permission.name")`

Todo contexto autenticado entrega `user_id`, `organization_id`, `role`, `permissions` e `plan`.
