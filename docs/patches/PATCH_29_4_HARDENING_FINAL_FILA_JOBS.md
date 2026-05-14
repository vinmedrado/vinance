# FinanceOS — PATCH 29.4

Hardening Final da Fila de Jobs (Performance + Estabilidade)

Implementado:
- `AGING_RECALC_INTERVAL_SECONDS = 30`
- aging recalculado apenas para jobs `queued`
- uso de `last_queue_check_at` para evitar recalculo em loop constante
- índices SQLite:
  - `idx_jobs_status_priority`
  - `idx_jobs_created_at`
  - `idx_jobs_type_status`
- campo opcional `is_stale_running`
- detecção de jobs `running` possivelmente travados após 2 horas
- limpeza segura de histórico antigo com confirmação na UI
- contagem de candidatos antes de limpar
- resumo operacional na página de jobs:
  - jobs em execução
  - jobs na fila
  - jobs com erro
  - jobs possivelmente travados
  - tempo médio de execução nos últimos 7 dias
- seção “Últimos erros”
- logs leves em `result_json._queue_events` para aging, stale running e cleanup

Não alterado:
- estratégia
- backtest
- `multi_factor.py`
- `strategy_runner.py`
- scripts `sync_*`
- comportamento funcional principal da fila

Execução:
`streamlit run legacy_streamlit/app.py`
