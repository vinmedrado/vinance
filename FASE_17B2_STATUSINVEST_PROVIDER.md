# Fase 17B-2 — Provider Real Status Invest

## Objetivo

Implementar o provider operacional do Status Invest para fundamentos de **ações** e **FIIs**, mantendo a estratégia aprovada nas fases de pesquisa: JSON-first, fallback HTML leve apenas para campos ausentes, persistência incremental e execução resiliente via Celery.

## Arquivos criados

- `backend/app/market/providers/statusinvest.py`
- `backend/app/market/parsers/statusinvest_html.py`
- `backend/app/market/parsers/__init__.py`
- `backend/app/market/normalizers/statusinvest.py`
- `backend/app/market/normalizers/__init__.py`
- `backend/app/market/services/statusinvest_service.py`
- `backend/tests/test_statusinvest_provider.py`

## Arquivos alterados

- `backend/app/market/scheduler/tasks.py`
- `backend/app/core/celery.py`

## Endpoints usados

Fonte principal:

- `GET https://statusinvest.com.br/category/advancedsearchresult`

Páginas HTML usadas somente como fallback leve:

- `GET https://statusinvest.com.br/acoes/{ticker}`
- `GET https://statusinvest.com.br/fundos-imobiliarios/{ticker}`

Não foi criado scraping DOM pesado, Selenium, Playwright, proxy, cookie fixo ou bypass anti-bot.

## Provider criado

`StatusInvestClient` implementa:

- `get_advanced_search()`
- `get_acoes_batch()`
- `get_fiis_batch()`
- `get_asset_page()`

Características:

- `httpx.AsyncClient`
- headers conservadores
- timeout
- retry exponencial com `tenacity`
- cooldown após `429`
- circuit breaker simples após `403` persistente
- concorrência baixa
- sem cookies fixos
- sem bypass

## Fields confirmados/mapeados

### Ações

Mapping explícito em `backend/app/market/normalizers/statusinvest.py`:

- `p_L` → `pl`
- `p_VP` → `pvp`
- `p_SR` → `psr`
- `eV_Ebitda` → `ev_ebitda`
- `eV_Ebit` → `ev_ebit`
- `margemLiquida` → `margem_liquida`
- `margemEbitda` → `margem_ebitda`
- `dy` → `dy_12m`
- `dividaLiquidaEbitda` → `divida_liq_ebitda`
- `liquidezMediaDiaria` → `volume_medio_diario`
- `valorMercado` → `market_cap`

### FIIs

- `p_VP` → `pvp`
- `dy` → `dy_12m`
- `liquidezMediaDiaria` → `liquidez_diaria`
- `patrimonioLiquido` / `valorPatrimonial` → `patrimonio_liq`
- `vpa` → `vpa`
- `segmento` / `segment` → `segmento`
- `tipo` → `tipo`
- `numCotistas` → `num_cotistas`

Campos desconhecidos retornam `None` ou são ignorados. Nenhum dado é inventado.

## Fallback HTML

Criado em `backend/app/market/parsers/statusinvest_html.py`.

FIIs:

- `vacancia_fisica`
- `vacancia_financeira`
- `gestora`
- `taxa_adm`
- `num_imoveis`

Ações:

- apenas campos ausentes realmente úteis, como margem e múltiplos complementares.

O parser usa BeautifulSoup com labels semânticos, sem selectors CSS longos e frágeis.

## Persistência incremental

Service oficial:

- `sync_statusinvest_acoes_from_catalog()`
- `sync_statusinvest_fiis_from_catalog()`

Regras:

- lê `asset_catalog`
- filtra somente `market='acoes'` e `market='fii'`
- processa em chunks de até 300 ativos
- upsert por `ticker`, `date` e `source`
- commit incremental por batch
- falha parcial não quebra o lote inteiro

## Source confidence

Como não foi criada migration nova, a confiança é refletida no campo `source` existente:

- `statusinvest_json`
- `statusinvest_html_fallback`
- `statusinvest_missing` reservado para classificação operacional futura

Além disso, os summaries das tasks contam:

- `json`
- `html_fallback`
- `missing`

## Celery

Tasks criadas:

- `market.sync_statusinvest_acoes_fundamentals`
- `market.sync_statusinvest_fiis_fundamentals`

Beat schedule:

- ações: diariamente às 21h30
- FIIs: diariamente às 22h00
- timezone: `America/Sao_Paulo`, herdado de `settings.celery_timezone`

## Estratégia anti-bot conservadora

- baixa concorrência
- sleep entre requests
- sleep entre batches
- retry exponencial
- cooldown após 429
- parada controlada após 403 persistente
- sem bypass
- sem browser automation operacional

## Testes criados

- normalização de ações
- normalização de FIIs
- parser fallback FII
- parser fallback ação
- `source_confidence`
- chunk/batch size
- fallback HTML controlado
- erro 429 tratado sem chamada real ao Status Invest

## Limitações atuais

- BDR e ETF ficaram fora por regra de escopo.
- O endpoint interno pode mudar payload/nomes de campos sem aviso.
- HTML fallback depende de labels textuais, ainda que sem selectors frágeis.
- Sem Playwright operacional por decisão de arquitetura e menor risco operacional.

## Por que BDR/ETF ficaram fora

A Fase 17B-2 foi limitada a ações e FIIs para reduzir risco de instabilidade e confirmar a operação contínua do provider Status Invest antes de ampliar o escopo. BDRs e ETFs devem ser avaliados em fase própria após estabilização de ações/FIIs.

## Validação executada

- `python -m compileall backend/app scripts workers`
- `pytest` tentado; bloqueado no sandbox por ausência de dependências de runtime (`sqlalchemy`, `celery`, `tenacity`).
- Backend startup não executado no sandbox pelo mesmo motivo.
- Celery worker/beat startup não executados no sandbox por ausência de `celery`.

## Riscos remanescentes

- Bloqueios eventuais por 403/429 em execução real.
- Mudança de CategoryType ou payload interno pelo Status Invest.
- Necessidade futura de ajustar o fallback HTML caso labels mudem.

## Próxima fase sugerida

Fase 17C:

- validação operacional em ambiente local com rede real
- coleta controlada de poucos tickers
- análise de logs 403/429
- ajuste de batch/delay antes de execução ampla
