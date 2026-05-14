# Multi-tenancy

O tenant oficial é `organizations.id`.

Todas as rotas financeiras do ERP filtram por `organization_id` e usam helpers tenant-safe para leitura, criação, edição e soft delete. Dados de despesas, receitas, contas, cartões, orçamento, metas, investimentos, alertas, jobs, analytics, audit logs e subscriptions devem sempre carregar `organization_id`.

Regra de segurança: nenhuma query de negócio deve acessar dados financeiros sem filtro `organization_id`.
