# Fase 3 — Catálogo de Ativos

## Status

Fase 3 implementada sobre a Fase 2 aprovada, mantendo o escopo restrito ao catálogo base de ativos locais.

Não foram criados providers externos, scraping, coleta de mercado, `asset_prices`, tabelas de fundamentos, ML, advisor IA, recomendações de investimento ou alterações no frontend.

## Arquivos criados

- `backend/app/catalog/__init__.py`
- `backend/app/catalog/models.py`
- `backend/app/catalog/schemas.py`
- `backend/app/catalog/service.py`
- `backend/app/catalog/router.py`
- `backend/alembic/versions/0003_create_asset_catalog.py`
- `data/catalogs/fiis.csv`
- `data/catalogs/acoes.csv`
- `data/catalogs/etfs.csv`
- `data/catalogs/bdrs.csv`
- `data/catalogs/criptos.csv`
- `data/catalogs/renda_fixa.csv`
- `scripts/seed_catalog.py`
- `backend/tests/test_catalog_module.py`
- `FASE_3_CATALOGO_ATIVOS.md`

## Arquivos alterados

- `backend/app/api/v1/router.py`
  - Registrado o router do catálogo em `/api/v1/catalog`.
- `backend/app/models.py`
  - Incluído `AssetCatalog` na agregação de modelos oficiais.
- `backend/alembic/env.py`
  - Incluído import do modelo `AssetCatalog` para garantir metadata única no Alembic.

## Migration criada

- `0003_create_asset_catalog.py`

A migration cria apenas a tabela `asset_catalog`, com:

- `id`
- `ticker`
- `name`
- `market`
- `sector`
- `segment`
- `currency`
- `exchange`
- `source`
- `is_active`
- `created_at`
- `updated_at`

Também cria:

- unique constraint composta `ticker + market`
- índice em `market`
- índice em `ticker`
- índice em `is_active`

A migration não altera tabelas de auth, financial ou qualquer estrutura de mercado/preços/fundamentos.

## Endpoints implementados

Prefixo: `/api/v1/catalog`

Endpoints públicos:

- `GET /api/v1/catalog`
- `GET /api/v1/catalog/{market}/{ticker}`

Endpoints autenticados:

- `POST /api/v1/catalog`
- `PUT /api/v1/catalog/{market}/{ticker}`
- `DELETE /api/v1/catalog/{market}/{ticker}`

O `DELETE` é lógico e apenas define `is_active = false`.

## Formato dos CSVs

Todos os CSVs em `data/catalogs/` seguem o mesmo header:

```csv
ticker,name,market,sector,segment,currency,exchange,source,is_active
```

Mercados oficiais aceitos:

- `fii`
- `acoes`
- `etf`
- `bdr`
- `cripto`
- `renda_fixa`

## Situação dos CSVs

Os CSVs são parciais e servem apenas como bootstrap inicial local.

Eles não representam catálogo oficial completo da B3, Tesouro Direto, criptoativos ou qualquer provedor externo. A coluna `source` foi preenchida com `bootstrap_manual_partial` para deixar claro que não há coleta externa nesta fase.

## Funcionamento do seed

Script criado:

```bash
python scripts/seed_catalog.py
```

Responsabilidades:

- ler arquivos CSV de `data/catalogs/`
- validar colunas obrigatórias
- normalizar ticker para uppercase
- normalizar market para valores oficiais
- aplicar currency default quando necessário
- evitar duplicatas no lote local
- inserir novos registros
- atualizar registros existentes pelo par `ticker + market`
- exibir resumo de arquivos processados, inseridos, atualizados, ignorados e erros de validação

O script usa a configuração de banco centralizada da Fase 1 via `DATABASE_URL`.

## Testes criados

Arquivo:

- `backend/tests/test_catalog_module.py`

Cobertura:

- normalização de ticker uppercase/trim
- rejeição de market inválido
- criação de asset via endpoint autenticado
- listagem com filtro `market`
- busca por `ticker/market`
- update de asset autenticado
- delete lógico autenticado
- validação de colunas obrigatórias do seed
- deduplicação local do seed

## Validação executada

Executado com sucesso:

```bash
python -m compileall backend/app scripts workers
pytest
alembic heads
```

Resultado:

- `compileall` OK
- `pytest` OK — 22 testes passaram
- `alembic heads` OK — head atual `0003_create_asset_catalog`

Não foi possível concluir neste ambiente:

```bash
alembic upgrade head
python scripts/seed_catalog.py
iniciar backend com /health real
validar endpoints com Postgres/Redis reais
```

Motivo: o ambiente de execução não possui Docker instalado e não há serviços `postgres`/`redis` ativos/resolvíveis. O erro observado ao tentar `alembic upgrade head` e `python scripts/seed_catalog.py` foi falha de resolução do host `postgres`, esperado fora do `docker compose`.

## Riscos remanescentes

- A validação real de migration e seed precisa ser executada localmente com `docker compose up --build`.
- Os CSVs são intencionalmente parciais; a completude do catálogo deverá ser tratada em fase própria, sem misturar com coleta de dados de mercado.
- A política de permissão para criação/edição/exclusão lógica está mínima: exige usuário autenticado, mas ainda não há RBAC administrativo.

## Preparado para Fase 4

A Fase 3 deixa preparado:

- modelo base de catálogo por `ticker + market`
- CSVs locais padronizados
- seed idempotente
- endpoints públicos de leitura
- endpoints autenticados de manutenção
- migration isolada

A próxima fase pode avançar para estrutura de mercado/preços ou providers somente se explicitamente aprovada, mantendo separação entre catálogo e coleta externa.
