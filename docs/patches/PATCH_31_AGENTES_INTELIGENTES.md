# FinanceOS — PATCH 31

Sistema de Agentes Inteligentes (IA aplicada ao FinanceOS)

Incluído:
- `services/agents/base_agent.py`
- `services/agents/agent_analyst.py`
- `services/agents/agent_risk.py`
- `services/agents/agent_catalog.py`
- `services/agents/agent_strategy.py`
- `services/agents/agent_explainer.py`
- `services/agents/agent_manager.py`
- `pages/14_Analise_Inteligente.py`

Características:
- agentes trabalham sobre dados já existentes
- fallback local sem API obrigatória
- suporte opcional a OpenAI-compatible API via variáveis de ambiente
- agentes retornam JSON estruturado + texto explicativo
- orquestrador salva `result_json["agents"]`
- página dedicada para análise inteligente

Não alterado:
- backtest
- multi_factor.py
- strategy_runner.py
- scripts existentes
- fila/jobs/orquestrador principal
- execução de trades

Execução:
`streamlit run legacy_streamlit/app.py`
