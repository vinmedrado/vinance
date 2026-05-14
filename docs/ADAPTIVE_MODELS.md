# Adaptive Budget Models

O `AdaptiveBudgetModelService` reavalia automaticamente o modelo financeiro conforme renda, despesas, dívidas, reserva e histórico.

## Fluxo

1. coleta dados reais do ERP por `organization_id`
2. chama `BudgetModelAdvisorService`
3. calcula saúde financeira
4. compara com snapshot anterior
5. informa se houve migração de modelo

Exemplo: Base Zero → 60/30/10 → 50/30/20 conforme dívidas caem, reserva cresce e sobra mensal melhora.
