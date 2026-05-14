# FinanceOS — PATCH 30.1

Ajustes finais do Orquestrador Geral.

Incluído:
- validação clara de retorno dos scripts:
  - returncode
  - stdout
  - stderr
- etapas com returncode != 0 viram `failed`
- etapas com returncode 0 e stdout vazio viram `warning`
- helper `classify_step_error(stderr, stdout)`
- retry simples para etapas não críticas:
  - máximo 1 retry
  - apenas para `api_error` e `timeout`
  - não aplica em schema/script_missing/invalid_args
- `retry_non_critical_steps` com default true
- resumo executivo final em result_json:
  - mode
  - status
  - total_steps
  - success_steps
  - failed_steps
  - warning_steps
  - skipped_steps
  - duration_seconds
  - critical_failures
  - non_critical_failures
  - final_message
- alerta forte para modo pesquisa
- confirmação obrigatória para modo pesquisa
- cards executivos na página 13

Não alterado:
- backtest
- multi_factor.py
- strategy_runner.py
- sistema de jobs
- fila
- scripts existentes

Execução:
`streamlit run legacy_streamlit/app.py`
