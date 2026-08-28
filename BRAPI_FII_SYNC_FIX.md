# Correção operacional — Sync Brapi FIIs e fallback por ticker

## Objetivo
Corrigir apenas o fluxo de sincronização Brapi para evitar erro HTTP 400 quando FIIs são enviados em lote.

## Arquivos alterados
- `backend/app/market/services/brapi_service.py`
- `backend/app/market/providers/brapi.py`

## Ajustes realizados
- O sync Brapi agora agrupa ativos por `market`: `acoes`, `bdr`, `etf` e `fii`.
- FIIs são sempre processados ticker por ticker.
- Demais mercados continuam em chunks pequenos.
- Quando um chunk retorna HTTP 400, o serviço aciona fallback ticker por ticker.
- A task não aborta quando um ticker falha.
- O retorno inclui `failed_tickers`, `invalid_tickers`, `failed_batches`, `fallback_batches` e resumo por mercado.
- Logs passam a registrar mercado, quantidade de ativos, modo de processamento, falhas e fallback acionado.

## Não alterado
- Frontend
- Advisor
- Financial
- Migrations
- Models
- Status Invest
- CoinGecko
- ML
- Celery beat
- Regras de negócio

## Validação executada
- `python -m compileall backend/app scripts workers`: OK

## Validação operacional recomendada
```bash
docker compose up -d --build
docker compose exec backend celery -A backend.app.core.celery.celery_app call market.sync_b3_quotes
```

Nos logs do worker, FIIs devem aparecer em modo individual e chunks HTTP 400 devem acionar fallback por ticker.
