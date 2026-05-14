# FinanceOS — PATCH 29.3

Aging de Prioridade e Anti-Starvation da Fila de Jobs.

Implementado:
- `AGING_INTERVAL_MINUTES = 10`
- `AGING_BONUS_MAX = 5`
- `effective_priority = priority + aging_bonus`
- `aging_bonus = floor(tempo_em_fila_minutos / AGING_INTERVAL_MINUTES)`, limitado por `AGING_BONUS_MAX`
- Campos adicionados se não existirem:
  - `effective_priority`
  - `last_queue_check_at`
  - `queue_reason` já preservado
- Ordenação da fila:
  1. `effective_priority DESC`
  2. `priority DESC`
  3. `created_at ASC`
- Recalculo de prioridade efetiva antes da seleção da fila, dentro do lock global.
- Aging não ignora limite global, limite por tipo ou cancelamento.
- UI de jobs mostra:
  - priority
  - effective_priority
  - aging_bonus
  - queue_reason
  - tempo em fila
  - alerta para job queued antigo

Não implementado neste patch:
- Celery
- Redis
- cron
- scheduler diário
- workers externos

Execução:
`streamlit run legacy_streamlit/app.py`
