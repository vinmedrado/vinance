# FinanceOS — PATCH 26.1

Otimização, cache e estabilidade do catálogo de ativos.

## Incluído

- Campos opcionais no `asset_catalog`:
  - `preferred_source`
  - `last_source_used`
  - `source_priority`
- Validação com cache via `--max-age-days`
- Validação forçada via `--force`
- Prioridade de fontes por classe de ativo
- Estados adicionais: `stale` e `weak_data`
- Score de qualidade mais restritivo
- Pipeline controlado do catálogo:
  - `scripts/update_catalog_pipeline.py`
- UI do Catálogo com filtros de fonte/status e estabilidade
- Saúde do Sistema com seção “Estabilidade do Catálogo”

## Execução

```bash
python scripts/update_catalog_pipeline.py --limit=500 --max-age-days=7
python scripts/update_catalog_pipeline.py --limit=500 --force
streamlit run legacy_streamlit/app.py
```
