# FinanceOS — PATCH 33

Histórico Inteligente e Comparação entre Execuções

Incluído:
- `services/intelligence_history_service.py`
- comparação entre execuções inteligentes
- cálculo de delta de score
- detecção de tendência:
  - improving
  - stable
  - worsening
  - first_run
- comparação de:
  - global_intelligence_score
  - retorno
  - drawdown
  - turnover
  - qualidade do catálogo
  - número de alertas
  - número de oportunidades
  - status geral
- integração com `agent_manager`
- persistência em `orchestrator_runs.result_json["intelligence_history"]`
- seção “Evolução da Inteligência” na página 14
- resumo de score/delta na Home
- resumo de evolução na página do Orquestrador

Não implementado:
- auto-ajuste de estratégia
- decisões automáticas
- trading
- ML

Execução:
streamlit run legacy_streamlit/app.py
