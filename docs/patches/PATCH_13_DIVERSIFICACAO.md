# PATCH 13 — Diversificação

Incluído controle de concentração sem alterar scoring, filtros existentes ou execução de lucro.

## Ajustes

- `max_position_pct` padrão reduzido para 15%.
- Política simples de diversificação em `backend/app/backtest/diversification.py`.
- `multi_factor` limita no máximo 2 ativos por setor quando há alternativas.
- Se o universo filtrado ficar pequeno, completa pelo menos 3–5 ativos quando houver candidatos disponíveis.
- Logs adicionados:
  - `% por ativo` (`allocation_pct`, `target_allocation_pct`)
  - concentração total
  - ativos excluídos por limite setorial
  - ativos incluídos por diversificação forçada

## Validação

```bash
python scripts/run_strategy_backtest.py --strategy=multi_factor --asset-class=equity --top-n=5 --mode=research
```

