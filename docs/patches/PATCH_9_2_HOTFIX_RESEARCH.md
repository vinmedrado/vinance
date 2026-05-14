# PATCH 9.2 — Hotfix do modo research no Backtest

Correção aplicada no `BacktestRepository`:

- `mode=research` não aplica filtro temporal em `asset_scores` nem em `asset_rankings`.
- O modo research busca o último snapshot disponível por ativo/ticker.
- O modo `no_lookahead` permanece protegido com `calculated_at <= data simulada`.
- A seleção `score_top_n` usa `asset_rankings` quando existir e cai para `asset_scores` quando não houver rankings válidos.
- A filtragem por `asset_class` agora usa fallback pela tabela `assets` quando a coluna da tabela de score/ranking estiver vazia.
- Diagnóstico inclui `temporal_filter_applied` para confirmar se o filtro temporal foi aplicado.

Comando esperado:

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --top-n=3 --mode=research
```

Logs esperados quando houver scores e preços:

- `scores_found > 0`
- `selected_tickers` preenchido
- `orders_generated > 0`
- `trades > 0`

Observação: se `scores_found` continuar 0 em research, o banco ainda não possui scores compatíveis com o filtro informado. Rode antes:

```bash
python scripts/run_analysis_engine.py --asset-class=equity --limit=20
```
