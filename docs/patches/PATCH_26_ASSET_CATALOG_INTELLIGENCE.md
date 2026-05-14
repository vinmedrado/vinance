# PATCH 26 — Inteligência do Catálogo de Ativos

Implementa camada incremental de qualidade e ranking do `asset_catalog` sem alterar backtest, banco legado ou estratégias.

## Incluído

- Novos campos de qualidade no `asset_catalog` via `ALTER TABLE` seguro.
- `services/asset_quality_service.py`
- `services/asset_ranking_service.py`
- `scripts/update_asset_quality_scores.py`
- Página de Catálogo com recomendações, top ativos e status de confiabilidade.
- Página de Saúde do Sistema com bloco de saúde do catálogo.

## Execução

```bash
python scripts/update_asset_quality_scores.py --limit=500
streamlit run legacy_streamlit/app.py
```
