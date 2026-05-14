# FinanceOS — PATCH 30

Orquestrador Geral “Rodar Tudo”

Incluído:
- Página `pages/13_Orquestrador_Geral.py`
- Serviço `services/financeos_orchestrator.py`
- Tabelas:
  - `orchestrator_runs`
  - `orchestrator_steps`
- Job type:
  - `financeos_orchestrator`
- Modos:
  - rápido
  - completo
  - pesquisa
- Execução via background_jobs e fila local existente
- Progresso por etapa
- Registro de logs stdout/stderr tail por etapa
- Falha parcial visível sem travar app
- Integração em:
  - `pages/0_Visao_Geral.py`
  - `pages/8_Saude_do_Sistema.py`

Não incluído:
- scheduler diário
- cron
- Celery/Redis
- worker externo
- agentes de IA

Execução:
`streamlit run legacy_streamlit/app.py`
