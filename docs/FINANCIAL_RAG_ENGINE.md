# Financial RAG Engine

O RAG financeiro interno recupera contexto relevante sem depender de embeddings pagos.

## Fontes
- Situação financeira atual.
- Score/fase financeira.
- Modelo de orçamento.
- Memória financeira.
- Comportamento.
- Forecast.
- Metas.
- Alertas.
- Próximos passos.
- Conversas anteriores.

## Fallback semântico local
Enquanto embeddings externos não forem ativados, o Vinance usa:
- palavras-chave;
- sobreposição textual;
- peso por entidade;
- recência;
- compactação de contexto.

## Objetivo
Ajudar o advisor a responder livremente sem virar FAQ fixo.
