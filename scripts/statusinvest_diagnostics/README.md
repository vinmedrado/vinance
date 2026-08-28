# Status Invest Diagnostics

Scripts isolados para a Fase 17B-1 do Vinance v2.

Eles servem apenas para confirmar payloads, `CategoryType`, headers mínimos e formato JSON do endpoint público `category/advancedsearchresult` antes da criação de um provider definitivo.

## Execução

```bash
python scripts/statusinvest_diagnostics/test_acoes_search.py
python scripts/statusinvest_diagnostics/test_fiis_search.py
```

Para salvar uma resposta bruta local em `temp/statusinvest/`:

```bash
python scripts/statusinvest_diagnostics/test_acoes_search.py --save-raw
python scripts/statusinvest_diagnostics/test_fiis_search.py --save-raw
```

## Regras

- Não acessa banco.
- Não persiste dados por padrão.
- Não integra Celery.
- Não cria provider operacional.
- Não usa cookie fixo, proxy, browser automation ou bypass anti-bot.
