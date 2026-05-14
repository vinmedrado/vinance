# PATCH 17 — Rebalance Threshold

Implementação incremental para reduzir micro-ajustes e turnover excessivo no Backtest Engine.

## Alteração principal

Arquivo alterado:

- `backend/app/backtest/strategies/strategy_runner.py`

## Parâmetro novo

- `rebalance_threshold_pct`
- default: `0.20`

## Regra

Para ajustes parciais, se:

```text
delta_pct = abs(target_value - current_value) / max(current_value, target_value, 1)
```

for menor que `rebalance_threshold_pct`, a ordem é ignorada.

## Exceções preservadas

- compra inicial não é bloqueada
- venda total obrigatória não é bloqueada
- score, final_score, dynamic penalty, hysteresis, min hold, filtros, win rate e banco não foram alterados

## Logs adicionados

- `Ordem ignorada por rebalance_threshold`
- `Resumo rebalance_threshold`

