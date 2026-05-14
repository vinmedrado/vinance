# PATCH 15 — Anti-turnover / Hysteresis

Implementado como patch incremental sobre o estado atual validado do FinanceOS.

## Preservado
- `multi_factor` continua usando `final_score` no ranking.
- `DynamicSelectionPenalty` preservado com `selection_penalty_factor` default `4.0` e override via params.
- Filtros de risco relaxados preservados:
  - bloqueia apenas `distancia_mm200 < -0.20`.
  - bloqueia apenas `retorno_3m < -0.15`.
- Diversificação setorial preservada.
- Rebalanceamento, execução, win rate, banco e schema não foram alterados.

## Implementado
- Controle de turnover/hysteresis no `StrategyBacktestRunner`.
- Parâmetros opcionais:
  - `turnover_control_enabled` default `true`.
  - `hysteresis_buffer` default `2`.
  - `min_holding_period_rebalances` default `2`.
- CLI:
  - `--turnover-control-enabled`
  - `--disable-turnover-control`
  - `--hysteresis-buffer`
  - `--min-holding-period-rebalances`

## Regra
Se um ativo já está na carteira e ainda aparece no ranking dentro de `top_n + hysteresis_buffer`, ele é mantido para evitar venda desnecessária.

## Logs adicionados
- `selected_tickers_original`
- `selected_tickers_after_hysteresis`
- `kept_by_hysteresis`
- `sold_by_rank_exit`
- `turnover_estimated_before`
- `turnover_estimated_after`
- `hysteresis_buffer`
- `min_holding_period_rebalances`
