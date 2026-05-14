# PATCH 11 — Universo de ativos real

Este patch expande o universo operacional de ações brasileiras do FinanceOS sem alterar a lógica de backtest.

## O que foi ajustado

- Catálogo fallback `data/catalog_fallback/brazil_equities.csv` mantido com 100+ ações brasileiras.
- Tabela `assets` atualizada com universo equity B3.
- `scripts/sync_historical_prices.py` agora aceita `--asset-class`.
- Pipeline de preços filtra automaticamente por classe, mantendo `--limit`, `--tickers`, `--start-date`, `--end-date`, `--incremental` e `--dry-run`.
- Logs mostram total de ativos carregados, sucessos, falhas e ignorados.

## Comandos

Popular/atualizar catálogo massivo:

```bash
python scripts/sync_massive_catalog.py --source=fallback --asset-class=equity
```

Baixar histórico das ações:

```bash
python scripts/sync_historical_prices.py --asset-class=equity --start-date=2022-01-01
```

Conferir cobertura:

```bash
python scripts/report_data_coverage.py
```

## Observação

O ZIP não inclui dados inventados de preço. Os históricos são persistidos em `data/financas.db` ao rodar o pipeline com internet disponível.
