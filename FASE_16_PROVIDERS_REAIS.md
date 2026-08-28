# Fase 16 — Providers Reais (Brapi + CoinGecko)

## Objetivo
Implementar a primeira camada real de integração de mercado do Vinance v2 para ativos do catálogo aprovado, sem scraping, sem ML, sem alteração de frontend e sem alteração das regras financeiras.

## Providers criados
- `backend/app/market/providers/brapi.py`
  - `BrapiClient`
  - `get_quotes(tickers)`
  - `get_historical_quotes(ticker, range="3mo")`
  - `get_available_tickers()`
- `backend/app/market/providers/coingecko.py`
  - `CoinGeckoClient`
  - `get_market_data(ids)`
  - `get_historical_market_chart(id)`
  - `get_top_coins()`

## Endpoints públicos usados
- Brapi: `https://brapi.dev/api`
- CoinGecko: `https://api.coingecko.com/api/v3`

As chaves `BRAPI_API_KEY` e `COINGECKO_API_KEY` foram adicionadas como opcionais no ambiente. Nenhuma chave real foi incluída.

## Services criados
- `backend/app/market/services/brapi_service.py`
- `backend/app/market/services/coingecko_service.py`

Responsabilidades:
- ler ativos ativos do `asset_catalog`;
- filtrar por mercado aprovado;
- processar em lotes;
- normalizar payloads externos;
- persistir `asset_prices` e fundamentos cripto básicos;
- manter falhas controladas sem quebrar Celery.

## Integração com catálogo
A Fase 16 não usa universo hardcoded de tickers. A sincronização Brapi usa ativos do catálogo com mercados:
- `acoes`
- `fii`
- `etf`
- `bdr`

A sincronização CoinGecko usa ativos do catálogo com mercado:
- `cripto`

Para cripto, existe apenas uma ponte controlada de símbolo para `coin_id` para ativos já presentes no catálogo, necessária porque a API CoinGecko usa IDs como `bitcoin` e `ethereum`.

## Tasks Celery criadas
Arquivo alterado:
- `backend/app/market/scheduler/tasks.py`

Tasks:
- `market.sync_b3_quotes`
- `market.sync_crypto_market`

As tasks são resilientes: falhas parciais retornam resumo controlado e geram logs, sem derrubar o worker inteiro.

## Beat schedule
Arquivo alterado:
- `backend/app/core/celery.py`

Novos agendamentos:
- B3 diário às 21h com `crontab(hour=21, minute=0)`
- Cripto a cada 5 minutos com `crontab(minute="*/5")`

Timezone mantido em `America/Sao_Paulo` via configuração existente.

## Estratégia de batching
- batch máximo interno: 500 registros;
- batch de provider: 50 ativos por chamada/lote;
- commits incrementais aproveitando `bulk_upsert_asset_prices` existente;
- sleeps curtos entre lotes para reduzir risco de rate limit.

## Retry, rate limit e timeout
- `httpx.AsyncClient` assíncrono;
- timeout configurado por client;
- `tenacity` com backoff exponencial;
- tratamento explícito de HTTP 429;
- limite de concorrência com `asyncio.Semaphore`;
- fallback seguro com payload vazio/erro controlado.

## Persistência
- `asset_prices` via upsert existente com deduplicação por constraint única;
- `cripto_fundamentals` via upsert existente por `coin_id` + `date`;
- fundamentos Brapi avançados de ações/FIIs/ETFs/BDRs não foram inventados, porque a API de cotação não entrega todos os campos fundamentalistas necessários de forma equivalente ao modelo.

## Limitações Brapi free
- limites de rate podem variar por plano;
- alguns campos podem vir ausentes;
- dados fundamentalistas completos podem exigir endpoints/planos específicos;
- Brapi não substitui Status Invest para fundamentos ricos.

## Limitações CoinGecko free
- limite de requisições mais restrito;
- `coin_id` difere do ticker;
- alguns campos históricos/fundamentalistas podem vir ausentes;
- dados em BRL podem exigir chamadas adicionais ou conversão futura.

## Testes criados
- `backend/tests/test_phase16_providers.py`

Cobertura:
- normalização de payload Brapi;
- normalização de payload histórico Brapi;
- normalização de payload CoinGecko;
- fallback de timeout sem chamada real;
- validação de batch máximo;
- existência do beat schedule para B3 e cripto.

## Validação executada
- `python -m compileall backend/app scripts workers`: OK
- `pytest`: tentativa executada no sandbox, mas a coleta foi bloqueada por dependências Python ausentes no ambiente (`sqlalchemy`/`celery`). Os testes da Fase 16 foram criados sem chamadas externas reais.
- `backend startup`: não executado no sandbox pelo mesmo bloqueio de dependências Python.
- `celery worker/beat startup`: não executado no sandbox pelo mesmo bloqueio de dependências Python.
- `npm install`: OK
- `npm run build`: OK

## Fora do escopo por regra
- Status Invest;
- scraping;
- ML;
- tabelas `_ml_features`;
- backtest;
- frontend;
- advisor.

## Riscos remanescentes
- Limites reais das APIs podem exigir ajuste de batch/intervalo em produção;
- alguns ativos do catálogo podem não existir no provider;
- mapeamento amplo de `ticker` para `coin_id` deve evoluir com campo dedicado no catálogo em fase futura;
- fundamentos ricos de ações/FIIs/ETFs/BDRs ainda dependem de provider específico futuro.

## Preparado para Fase 17
- base assíncrona de providers;
- services isolados;
- tasks Celery resilientes;
- schedule operacional;
- contratos de normalização testáveis sem chamadas externas.
