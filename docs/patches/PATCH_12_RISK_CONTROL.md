# PATCH 12 — Controle de Risco no Backtest

Este patch adiciona controles de risco à estratégia `multi_factor` sem alterar cálculo de lucro, scoring base ou schema do banco.

## Implementado

- Filtro obrigatório de tendência em `multi_factor`: somente seleciona ativos com `price > mm200` ou `distancia_mm200 > 0`.
- Filtro obrigatório de momentum: exclui ativos com `retorno_3m < 0` usando `retorno_3m` ou fallback `retorno_90d`.
- Limite padrão de posição: `max_position_pct = 0.20`.
- Cash buffer padrão: 10% da carteira permanece fora da alocação alvo.
- Logs de ativos filtrados e motivo de exclusão.
- Logs de alocação atual e alvo por ativo no rebalanceamento.

## Validação

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=5 --mode=research
python scripts/report_backtest.py
```

## Observação

O modo `research` continua sendo apenas validação operacional e não backtest sem viés. O modo `no_lookahead` permanece intacto.
