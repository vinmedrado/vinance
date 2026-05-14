# FinanceOS — PATCH 29.2

Robustez da fila de jobs:
- Lock global em services/job_executor.py (`job_queue_lock`)
- Fila com prioridade funcional (`priority DESC`, `created_at ASC`)
- Limite global de concorrência (`MAX_CONCURRENT_JOBS = 2`)
- Limite por tipo (`JOB_TYPE_LIMITS`)
- Prevenção de duplicidade por job_type + hash de parâmetros
- Proteção de overload da fila (`MAX_QUEUE = 20`)
- Cancelamento seguro de jobs queued e cancelamento lógico de running
- Página de jobs atualizada com prioridade, tipo, motivo de fila e cancelamento em massa
- Sem scheduler, cron, Redis, Celery ou worker externo

Limitação intencional:
- Background local/thread-based. Se o Streamlit for fechado/reiniciado, jobs em execução podem parar.
