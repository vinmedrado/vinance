# FinanceOS — PATCH 30

Orquestrador Geral “Rodar Tudo”

Incluído:
- `pages/13_Orquestrador_Geral.py`
- `services/financeos_orchestrator.py`
- tabelas:
  - `orchestrator_runs`
  - `orchestrator_steps`
- job type:
  - `financeos_orchestrator`
- integração com fila local/thread-based existente
- integração com:
  - `pages/0_Visao_Geral.py`
  - `pages/8_Saude_do_Sistema.py`

Modos:
- rápido
- completo
- pesquisa

Não incluído:
- scheduler diário
- cron
- Celery/Redis
- workers externos
- agentes de IA

Execução:
`streamlit run legacy_streamlit/app.py`
