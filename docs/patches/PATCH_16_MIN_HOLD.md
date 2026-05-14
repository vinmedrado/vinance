# PATCH 16 — MIN HOLD / Tempo mínimo de permanência

Implementado controle incremental de tempo mínimo de permanência no backtest.

Alterado:
- backend/app/backtest/strategies/strategy_runner.py

Resumo:
- Ordem preservada: seleção original → hysteresis → min hold → rebalanceamento.
- `min_holding_period_rebalances` default = 2.
- Ativos com holding abaixo do mínimo não são vendidos no rebalanceamento.
- Logs adicionados: holding_periods, min_hold_blocked, sold_normally, selected_tickers_after_min_hold.
- Memória dinâmica continua usando a seleção final executável após hysteresis/min_hold.

Não alterado:
- score_original
- final_score
- penalização dinâmica
- filtros de risco
- diversificação setorial
- win rate
- banco de dados
- execução de ordens
