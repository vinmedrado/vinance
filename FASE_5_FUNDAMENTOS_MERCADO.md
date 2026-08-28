# Fase 5 — Fundamentos por Mercado

## Status

Fase 5 implementada a partir da Fase 4 aprovada (`vinance_v2_fase4_market_data`).

O objetivo desta fase foi criar a estrutura de dados fundamentalistas separada por mercado, mantendo o módulo `market` isolado e sem iniciar inteligência, recomendação, backtest, scraping ou providers externos novos.

## Arquivos criados

- `backend/app/market/models/fii.py`
- `backend/app/market/models/acoes.py`
- `backend/app/market/models/etf.py`
- `backend/app/market/models/bdr.py`
- `backend/app/market/models/cripto.py`
- `backend/alembic/versions/0005_create_market_fundamentals.py`
- `backend/tests/test_market_fundamentals.py`
- `FASE_5_FUNDAMENTOS_MERCADO.md`

## Arquivos alterados

- `backend/app/market/models/__init__.py`
- `backend/app/models.py`
- `backend/app/market/schemas.py`
- `backend/app/market/service.py`
- `backend/app/market/router.py`

## Migration criada

Migration:

- `0005_create_market_fundamentals.py`

Cria somente:

- `fii_fundamentals`
- `acoes_fundamentals`
- `etf_fundamentals`
- `bdr_fundamentals`
- `cripto_fundamentals`

Não altera tabelas financeiras, catálogo, `asset_prices`, `macro_indicators` ou `renda_fixa_produtos`.

## Tabelas criadas

### `fii_fundamentals`

Fundamentos específicos de fundos imobiliários, com campos como patrimônio líquido, VPA, P/VP, dividend yield, vacância, gestora, administradora e taxas.

Constraint:

- `UNIQUE ticker + date + source`

Índices:

- `ticker`
- `date`
- `segmento`
- `source`

### `acoes_fundamentals`

Fundamentos específicos de ações, com campos como market cap, PL, P/VP, EV/EBITDA, ROE, ROA, ROIC, margens, CAGR, dividend yield, payout e dívida líquida/EBITDA.

Constraint:

- `UNIQUE ticker + date + source`

Índices:

- `ticker`
- `date`
- `setor`
- `source`

### `etf_fundamentals`

Fundamentos específicos de ETFs, com campos como patrimônio líquido, índice replicado, taxa de administração, retornos, tracking error, tracking difference, cotistas e gestora.

Constraint:

- `UNIQUE ticker + date + source`

Índices:

- `ticker`
- `date`
- `indice_replicado`
- `source`

### `bdr_fundamentals`

Fundamentos específicos de BDRs, com campos como empresa subjacente, ticker original, bolsa de origem, país, moeda, câmbio, múltiplos e volume em BRL.

Constraint:

- `UNIQUE ticker + date + source`

Índices:

- `ticker`
- `date`
- `ticker_original`
- `source`

### `cripto_fundamentals`

Fundamentos específicos de criptoativos, com `coin_id`, preços em BRL/USD, market cap, rank, volume, variações percentuais, supply, ATH e dominância BTC.

Constraint:

- `UNIQUE coin_id + date`

Índices:

- `coin_id`
- `ticker`
- `date`
- `source`

## Endpoints adicionados

Todos são públicos e somente leitura:

- `GET /api/v1/market/fundamentals/fii`
- `GET /api/v1/market/fundamentals/acoes`
- `GET /api/v1/market/fundamentals/etf`
- `GET /api/v1/market/fundamentals/bdr`
- `GET /api/v1/market/fundamentals/cripto`

Filtros suportados:

- `ticker`
- `date_from`
- `date_to`
- `source`
- `limit`
- `offset`

## Decisão arquitetural: fundamentos separados por mercado

A Fase 5 manteve a decisão da auditoria: fundamentos não devem ser armazenados em uma tabela genérica única, porque cada mercado possui semântica, métricas, fontes e granularidade próprias.

Por isso, não foi criada nenhuma tabela `asset_fundamentals`. A separação evita colunas genéricas demais, excesso de campos nulos e ambiguidade entre métricas de FIIs, ações, ETFs, BDRs e criptoativos.

## O que NÃO foi implementado de propósito

- Nenhuma tabela `asset_fundamentals` genérica.
- Nenhuma tabela `*_ml_features`.
- Nenhum ML.
- Nenhuma recomendação.
- Nenhum advisor IA.
- Nenhum backtest.
- Nenhum ranking.
- Nenhum scoring de ativos.
- Nenhum scraping.
- Nenhum provider externo novo.
- Nenhuma integração com Status Invest.
- Nenhuma alteração no frontend.
- Nenhuma alteração no módulo financeiro.
- Nenhuma alteração funcional em `asset_prices`.

## Service

Foram adicionadas funções de leitura:

- `list_fii_fundamentals`
- `list_acoes_fundamentals`
- `list_etf_fundamentals`
- `list_bdr_fundamentals`
- `list_cripto_fundamentals`

Foram adicionadas funções internas de upsert para uso futuro por providers:

- `upsert_fii_fundamental`
- `upsert_acao_fundamental`
- `upsert_etf_fundamental`
- `upsert_bdr_fundamental`
- `upsert_cripto_fundamental`

As funções de upsert apenas persistem dados normalizados. Elas não chamam APIs externas e não executam coleta.

## Testes criados

Arquivo:

- `backend/tests/test_market_fundamentals.py`

Cobertura adicionada:

- metadata contém as cinco tabelas novas;
- não existe `asset_fundamentals`;
- não existem tabelas `*_ml_features`;
- constraints unique por mercado existem;
- upsert normaliza ticker/source e não duplica;
- limite de lote maior que 500 é rejeitado;
- índices esperados existem;
- endpoint retorna lista vazia sem erro;
- endpoint de recomendações não existe.

## Validação executada

Executado no ambiente local do pacote:

```bash
python -m compileall backend/app scripts workers
pytest -q
alembic heads
```

Resultado:

- Compile Python: OK
- Pytest: `40 passed`
- Alembic head: `0005_create_market_fundamentals`

Validações que dependem de serviços reais não foram executadas neste ambiente porque não há Docker/Postgres/Redis ativos:

- `alembic upgrade head`
- iniciar backend real
- validar `/health` contra banco/Redis reais
- validar endpoints com banco real

A estrutura e os testes isolados foram mantidos compatíveis com a execução local via Docker Compose.

## Riscos remanescentes

- Os dados reais ainda dependem de providers futuros.
- Sem coleta real, as tabelas estarão vazias após migration.
- A padronização final de fontes precisa ser definida quando os providers de fundamentos forem implementados.
- Métricas específicas podem exigir ajustes de precisão conforme fonte real.

## Preparado para Fase 6

A Fase 5 deixa preparado:

- base relacional separada por mercado;
- endpoints públicos de leitura;
- serviços internos de upsert para providers futuros;
- constraints e índices por mercado;
- proteção arquitetural contra tabela genérica e contra acoplamento prematuro com ML/recommendations/advisor.

A próxima fase pode implementar coleta real de fundamentos por provider autorizado, mantendo os services como camada de persistência.
