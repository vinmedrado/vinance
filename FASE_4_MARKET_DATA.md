# Fase 4 — Market Data mínimo viável

## Status
Fase 4 implementada com base de dados de mercado, providers permitidos, tasks Celery e endpoints públicos mínimos. Não foram criadas features de ML, recomendações, advisor, scraping, fundamentos ou tabelas de features.

## Arquivos criados
- `backend/app/market/models/__init__.py`
- `backend/app/market/models/prices.py`
- `backend/app/market/models/macro.py`
- `backend/app/market/models/renda_fixa.py`
- `backend/app/market/providers/__init__.py`
- `backend/app/market/providers/bcb.py`
- `backend/app/market/providers/tesouro.py`
- `backend/app/market/providers/yfinance.py`
- `backend/app/market/scheduler/__init__.py`
- `backend/app/market/scheduler/tasks.py`
- `backend/app/market/schemas.py`
- `backend/app/market/service.py`
- `backend/app/market/router.py`
- `backend/alembic/versions/0004_create_market_data_base.py`
- `backend/tests/test_market_module.py`
- `FASE_4_MARKET_DATA.md`

## Arquivos alterados
- `backend/app/api/v1/router.py`: registro do router público `/api/v1/market`.
- `backend/app/models.py`: inclusão dos modelos de market data na metadata única.
- `backend/app/core/celery.py`: registro das tasks de market e configuração do Beat.

## Migration criada
- `0004_create_market_data_base.py`

A migration cria somente:
- `asset_prices`
- `macro_indicators`
- `renda_fixa_produtos`

Não altera tabelas de auth, financial ou catalog.

## Providers implementados
- `bcb.py`: provider assíncrono para SELIC, IPCA e CDI via API pública do Banco Central.
- `tesouro.py`: provider assíncrono para produtos do Tesouro Direto via endpoint JSON público.
- `yfinance.py`: provider assíncrono para preços históricos via Yahoo Chart API, sem scraping de HTML.

Não foram criados:
- `brapi.py`
- `coingecko.py`
- `statusinvest.py`

## Tasks Celery criadas
- `market.sync_macro_indicators`
- `market.sync_tesouro_direto`
- `market.sync_historical_prices_weekly`
- `market.cleanup_old_asset_prices`

## Celery Beat
Configurado em `backend/app/core/celery.py`:
- macro diário
- tesouro diário
- histórico semanal
- cleanup diário

As filas continuam separadas em:
- `default`
- `market`
- `intelligence`

## Endpoints criados
Prefixo: `/api/v1/market`

- `GET /api/v1/market/macro`
- `GET /api/v1/market/prices/{market}/{ticker}`
- `GET /api/v1/market/renda-fixa`

Todos são públicos nesta fase e não retornam recomendações, rankings ou advisor.

## Limites de lote
`bulk_upsert_asset_prices` trabalha com lote máximo de 500 registros.

A função `chunk_records` rejeita `batch_size > 500`, evitando carga sem controle.

## TTL de preços
Foi implementada a função:
- `cleanup_asset_prices_older_than_2_years`

O TTL lógico de preços é de 730 dias. A task diária `market.cleanup_old_asset_prices` executa essa limpeza.

## Testes criados
- metadata dos modelos/tabelas
- normalização de ticker
- bulk insert respeitando lote 500
- upsert sem duplicar
- cleanup com TTL de 2 anos
- upsert de macro indicator
- endpoints `/macro`, `/prices` e `/renda-fixa`
- import das tasks Celery sem erro

## Validação executada
Executado no ambiente local do pacote:

- `python -m compileall backend/app scripts workers`
- `pytest`
- `alembic heads`

Limitação do ambiente: não há Docker/Postgres/Redis ativos aqui, então `alembic upgrade head`, worker/beat reais e `/health` real com serviços externos devem ser validados localmente pelo usuário com Docker.

## Riscos remanescentes
- Providers externos podem variar formato de resposta ou disponibilidade; todos retornam lista vazia em falha para não quebrar o app.
- Yahoo Chart API foi mantida como fonte mínima para histórico, sem scraping; produção pode exigir provider pago/estável no futuro.
- Tesouro Direto pode alterar estrutura JSON; a normalização já ignora registros inválidos.
- O agendamento semanal usa intervalo fixo de 7 dias; ajuste fino de crontab pode ser feito depois se necessário.

## Preparado para a próxima fase
A Fase 4 deixa preparado:
- base de preços históricos com deduplicação
- indicadores macroeconômicos
- produtos de renda fixa
- Celery Beat operacional
- camada de providers isolada
- endpoints mínimos de leitura

Próxima fase recomendada: expansão controlada de fundamentos por classe de ativo ou coleta de dados de mercado mais completa, ainda antes de qualquer ML/recommendation/advisor.
