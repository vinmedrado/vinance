# AI RESPONSE SYSTEM

Este documento descreve o patch incremental do Vinance AI Copilot.

## Objetivo
Transformar o Advisor em um consultor financeiro conversacional, contextual e seguro, usando dados reais do ERP financeiro por organização/usuário.

## Princípios
- Não funciona como FAQ engessado.
- Usa contexto financeiro consolidado: renda, despesas, dívidas, orçamento, metas, reserva, score, fase, memória, comportamento, forecast e alertas.
- Mantém isolamento multi-tenant via organization_id/user_id.
- Não promete retorno, não emite ordem de compra/venda e prioriza organização financeira quando a saúde financeira está crítica.

## Componentes relacionados
- financial_ai_orchestrator.py
- financial_context_builder.py
- contextual_financial_memory.py
- financial_safety_guardrails.py
- continuous_financial_copilot.py
- user_learning_profile_service.py
- humanization_engine.py

## Disclaimer
O Vinance fornece análises educacionais baseadas nos dados do usuário e em simulações. Isso não constitui recomendação financeira individualizada.
