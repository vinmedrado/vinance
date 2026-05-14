# Frontend do Advisor

O Vinance usa dados reais do ERP financeiro por `organization_id` e `user_id` para gerar orientação educativa, contextual e segura.

## Princípios
- Não promete retorno.
- Não emite ordem de compra/venda.
- Prioriza reserva, dívidas e orçamento quando a saúde financeira está frágil.
- Mantém isolamento multi-tenant.
- Traduz análise em linguagem simples.

## Componentes
- `financial_context_builder.py`: consolida renda, despesas, metas, forecast, memória e comportamento.
- `conversational_financial_advisor.py`: responde perguntas do usuário com base no contexto.
- `continuous_financial_copilot.py`: gera eventos e alertas inteligentes.
- `user_learning_profile_service.py`: aprende preferências e desafios recorrentes.
- `financial_safety_service.py`: aplica guardrails e disclaimer.

## Disclaimer
O Vinance fornece análises educacionais baseadas nos seus dados e em simulações. Isso não constitui recomendação financeira individualizada.
