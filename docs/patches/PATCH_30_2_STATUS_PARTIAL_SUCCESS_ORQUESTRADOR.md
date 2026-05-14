# FinanceOS — PATCH 30.2

Alinhamento de status do Job com resultado parcial do Orquestrador.

Incluído:
- suporte a `partial_success` em `background_jobs`
- helper `finish_partial_success_job`
- `result_json.execution_outcome`
- `result_json.has_warnings`
- orquestrador finaliza job como:
  - success quando sucesso total
  - partial_success quando falha não crítica
  - failed quando falha crítica/estrutural
- página Jobs exibe:
  - badge amarelo “Concluído com alertas”
  - fallback visual quando status antigo é success mas result_json.execution_outcome = partial_success
- página Orquestrador exibe warning em partial_success
- `orchestrator_runs.status` preserva partial_success

Não alterado:
- backtest
- multi_factor.py
- strategy_runner.py
- fila de jobs
- scripts existentes
- lógica de estratégia
