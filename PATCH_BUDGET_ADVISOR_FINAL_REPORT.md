# Vinance Budget Advisor Final Patch

## Objetivo
Conectar o fluxo principal do Vinance ao comportamento esperado do produto: renda, despesas, dívidas, diagnóstico, modelo financeiro recomendado, plano mensal e capacidade segura para investir.

## Principais entregas

- `BudgetModelAdvisorService` com regras para Recuperação Financeira, Base Zero, 70/20/10, 60/30/10, 50/30/20 e modelo personalizado.
- Endpoint `POST /api/intelligence/budget-advisor` para simulação controlada.
- Endpoint `GET /api/intelligence/financial-plan` para cálculo real por `organization_id` com base no ERP.
- Snapshot opcional em `budget_advisor_snapshots`.
- Tela React `Meu Plano Financeiro` sem alterar branding.
- Integração do fluxo com investimentos via `investment_gate`.
- Testes unitários para os cenários exigidos.
- Documentação em `docs/BUDGET_MODEL_ADVISOR.md` e `docs/FINANCIAL_PLAN_FLOW.md`.

## Validação executada

- `python -m compileall backend/app tests/test_budget_model_advisor.py`: OK.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_budget_model_advisor.py`: 7 passed.

## Limitações

- `npm run build`, Docker e Alembic não foram executados integralmente neste ambiente.
- O cálculo de dívidas usa os dados disponíveis no ERP; quando não houver uma entidade específica de dívida, usa marcadores de descrição/categoria/status.
