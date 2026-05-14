# PATCH 10.1 — Estratégias realmente operacionais no backtest

Correções aplicadas:

- `score_top_n` mantém comportamento por `asset_scores`/`asset_rankings`.
- Parâmetros de peso e `require_above_mm200` agora geram log explícito quando usados em `score_top_n`, pois não se aplicam a essa estratégia.
- `multi_factor` agora chama o universo com `mode=research` corretamente.
- `multi_factor` calcula `factor_score` com base em `asset_analysis_metrics.metrics_json` e fallbacks dos scores persistidos.
- `multi_factor` respeita `asset_class`, `top_n`, `min_score`, `min_liquidity_score` e `require_above_mm200`.
- Runner de estratégias atualizado para usar rebalanceamento completo do PATCH 9.5:
  - calcula delta por ativo;
  - vende posições acima do alvo primeiro;
  - compra posições abaixo do alvo depois;
  - mantém caixa e posições entre rebalanceamentos.
- Logs por rebalance incluem:
  - strategy;
  - scores_found;
  - metrics_found;
  - selected_tickers;
  - factor_scores;
  - motivo quando não há seleção.

Comando validado por sintaxe:

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=3 --mode=research --weight-return=0.7 --weight-trend=0.3 --weight-risk=0 --weight-liquidity=0 --weight-dividend=0
```

Observação: se o banco local não tiver `asset_scores`, `asset_analysis_metrics` e `asset_prices`, o backtest continua diagnosticável e explica o motivo.
