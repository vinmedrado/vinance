# Memória Conversacional

A memória conversacional mantém continuidade entre interações do Advisor.

## Componentes
- `advisor_conversations`: sessões.
- `advisor_messages`: mensagens recentes.
- `advisor_memory_summaries`: resumo acumulado.
- `ConversationalMemoryService`: interface de leitura/escrita.

## O que é lembrado
- Temas recorrentes: dívidas, investimentos, metas, orçamento, reserva.
- Decisões discutidas.
- Dúvidas recorrentes.
- Contexto recente da conversa.

## Segurança
Toda chave de memória é isolada por `organization_id` e `user_id`. O serviço não mistura contexto entre organizações.
