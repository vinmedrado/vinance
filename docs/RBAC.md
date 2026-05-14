# RBAC

Roles oficiais:

- owner
- admin
- finance_manager
- analyst
- member
- viewer

Permissões sensíveis são aplicadas com `require_permission()` nas rotas financeiras e enterprise. `viewer` não cria, edita ou exclui. `member` não gerencia billing/admin. `owner` possui acesso total.
