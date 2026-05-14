# Audit Logs

Eventos são gravados por `audit_log_service.record_event(...)` / `record_audit_log(...)`.

Campos:

- organization_id
- user_id
- action
- entity_type
- entity_id
- before_json
- after_json
- ip_address
- user_agent
- request_id
- created_at

Eventos cobertos incluem auth, despesas, receitas, orçamento, usuários/RBAC, billing e jobs.
