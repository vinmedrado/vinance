# FinanceOS — Nova estratégia `momentum`

Implementação incremental da estratégia `momentum` sem alterar banco, scoring, multi_factor ou lógica de execução.

## Regras

- Filtra ativos com `price > mm200` usando `distancia_mm200 > 0` quando disponível.
- Filtra ativos com `retorno_3m > 0`, mapeado para `retorno_90d` no Analysis Engine.
- Score final = `retorno_6m`, mapeado para `retorno_180d`.
- Ordena por score final descendente e seleciona `top_n`.
- Usa o rebalanceamento existente do StrategyBacktestRunner.

## Comando de validação

```bash
python scripts/run_strategy_backtest.py --strategy=momentum --asset-class=equity --top-n=3 --mode=research
```

## Logs

Os logs aparecem como `factor_scores` para manter compatibilidade com o runner atual e incluem:

- `retorno_3m`
- `retorno_6m`
- `mm200_status`
- `score_final`
