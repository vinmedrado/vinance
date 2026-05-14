# PATCH 9.3 — Hotfix definitivo do modo research

Correção aplicada no Backtest Engine para o modo `research`:

- `research` não aplica filtro temporal em `asset_scores`.
- `research` busca scores atuais diretamente do banco.
- Filtro de `asset_class` é case-insensitive.
- Se `asset_class` zerar o resultado, o hotfix remove o filtro e usa todos os scores disponíveis.
- `source_used` passa a retornar `scores` quando scores forem usados.
- Diagnóstico inclui:
  - `scores_total_db`
  - `scores_after_filter`
  - `score_filter_applied`
  - `asset_class_filter_requested`
  - `asset_class_filter_effective`

Comando de validação:

```bash
python scripts/run_strategy_backtest.py --strategy=score_top_n --asset-class=equity --top-n=3 --mode=research
```

O modo `no_lookahead` foi mantido intacto e continua delegando para a lógica segura do PATCH 9.2.
