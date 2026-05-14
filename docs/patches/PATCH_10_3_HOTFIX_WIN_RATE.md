# PATCH 10.3 — Correção do Win Rate no Backtest

Correção focada apenas em métricas.

## Corrigido

- Win rate deixou de contar vendas isoladas como vitórias.
- Compra isolada não entra mais no cálculo de win rate.
- Posição aberta não entra no cálculo de win rate.
- Trades fechados são pareados por FIFO: `buy -> sell`.
- PnL considera custo de transação:
  - compra: `gross_value + transaction_cost`
  - venda: `gross_value - transaction_cost`
- Métricas adicionais no `metrics_json`:
  - `closed_trades`
  - `profitable_trades`
  - `losing_trades`
  - `avg_pnl_per_trade`
  - `total_closed_pnl`
  - `unmatched_sells`
  - `open_lots`
  - `open_quantity`

## Não alterado

- Estratégias
- Execução
- Scoring
- Banco/schema
- Rebalanceamento

## Validação

```bash
python scripts/report_backtest.py
```
