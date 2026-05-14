# FinanceOS — PATCH 35

Automação Inteligente de Rotinas

Incluído:
- `services/automation_service.py`
- `pages/16_Automacoes.py`
- tabelas:
  - `automation_rules`
  - `automation_runs`
- regras padrão:
  - catalog_update
  - market_data_update
  - orchestrator_run
  - intelligence_analysis
  - bi_refresh
  - health_check
- avaliação smart:
  - catálogo desatualizado/fraco
  - dados de mercado antigos/vazios
  - orquestrador sem execução recente
  - inteligência piorando
  - jobs com falha recente
- execução manual via jobs existentes:
  - catalog_full_pipeline
  - market_data_full_pipeline
  - financeos_orchestrator
- UI central de automações
- sugestões inteligentes com botão executar
- integração com Home
- integração com Saúde do Sistema

Não implementado:
- scheduler real em background
- execução automática sem clique
- trading
- decisões de investimento automáticas
- alteração automática de estratégia

Execução:
streamlit run legacy_streamlit/app.py
