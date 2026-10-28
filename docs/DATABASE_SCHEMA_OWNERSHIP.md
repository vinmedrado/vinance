# Database schema ownership

Este documento define quem cria, evolui e valida cada tabela PostgreSQL usada
pelo VinanceOS. Uma tabela necessária ao runtime deve pertencer ao Alembic
canônico ou ter ownership externo explícito. Estruturas criadas apenas por
scripts históricos não fazem parte do contrato suportado.

## Alembic canônico

O Alembic configurado em `alembic.ini`, com metadata em
`backend.app.core.database.Base`, é a fonte de verdade para o schema principal
da aplicação. Ele inclui autenticação, dados financeiros, household,
Recommendation/Intelligence e as decisões imutáveis do Autopilot 1–6.

As cinco tabelas de features Intelligence pertencem a esse domínio:

- `acoes_ml_features`;
- `bdr_ml_features`;
- `cripto_ml_features`;
- `etf_ml_features`;
- `fii_ml_features`.

Os models atuais em `backend/app/intelligence/models/` são o contrato dessas
tabelas. A migration `0025_intelligence_schema` reconcilia o formato genérico
criado em `0006` com esse contrato: adiciona as features específicas de cada
mercado, normaliza os campos numéricos e substitui constraints e índices
históricos pelos objetos canônicos.

A migration `0026_fixed_income_v1` evolui, no mesmo ownership canônico, a
tabela `renda_fixa_produtos` e o perfil financeiro. Ela acrescenta identidade
estável de origem, fatos de preço/taxa/liquidez/vencimento, metadata da fonte e
o horizonte opcional `financial_profiles.investment_horizon_months`. O
catálogo global continua separado de `owned_assets`: uma oportunidade de
mercado não prova propriedade pelo usuário.

Em `cripto_ml_features`, linhas legadas sem `coin_id` recebem um identificador
estável no formato `legacy:<ticker-normalizado>`. Esse prefixo registra a
proveniência sem fingir que o valor é um identificador nativo de provedor. A
migration falha se o backfill produzir duplicidade em `(coin_id, date)`.

No banco canônico já alinhado, o upgrade é estruturalmente idempotente por
introspecção e apenas avança a revisão. O downgrade para `0024` é permitido
somente quando as cinco tabelas estão vazias, pois remover colunas específicas
ou reduzir a precisão com dados presentes seria destrutivo.

## Trading V2 externo

Trading V2 usa um lifecycle externo versionado em
`backend/trading/storage/migrate.py`. As tabelas abaixo compartilham o schema
PostgreSQL `public`, mas não pertencem ao metadata nem ao lifecycle do Alembic
principal:

- `backtest_runs`;
- `crypto_candles`;
- `crypto_features`;
- `crypto_targets`;
- `paper_trades`;
- `trading_signals`.
- `trading_paper_accounts`;
- `trading_paper_orders`;
- `trading_paper_positions`;
- `trading_paper_events`;
- `trading_schema_version`;
- `trading_schema_migrations`.

`backend/trading/storage/schema.sql` permanece como referência histórica da
revisão inicial. Novos ambientes e upgrades usam exclusivamente o runner
externo. Ele mantém histórico e checksum por revisão, trava upgrades
concorrentes e falha fechado se a aplicação encontrar uma versão incompatível.

`backend/alembic/schema_ownership.py` é a lista canônica dessa exclusão. Uma
migration da aplicação não pode criar, alterar ou remover essas tabelas. Uma
tabela Intelligence não pode ser adicionada a essa lista para ocultar drift.

## Validação reproduzível

O gate normal é:

```bash
alembic current
alembic heads
alembic check
```

O resultado suportado possui um único head e nenhuma nova operação detectada.
Além do banco canônico, a cadeia inteira deve ser validada periodicamente em um
PostgreSQL vazio com `alembic upgrade head`.

O teste `backend/tests/test_alembic_fresh_database.py` automatiza essa prova.
Ele exige uma base PostgreSQL dedicada cujo nome contenha `test`, reconstrói
apenas o schema `public` dessa base, executa todas as migrations e compara o
resultado com o metadata, inclusive Intelligence e Renda Fixa, e confirma que
as seis tabelas externas do Trading não foram adotadas. Exemplo de execução
em ambiente isolado:

```bash
ALEMBIC_FRESH_TEST_DATABASE_URL=<url-de-banco-test-dedicado> \
pytest backend/tests/test_alembic_fresh_database.py
```

Nunca aponte essa variável para o banco canônico. Testes de downgrade também
devem usar banco isolado e vazio.

## Regra para evoluções futuras

1. inspecionar o schema canônico e o metadata;
2. confirmar o owner da tabela;
3. revisar manualmente a migration;
4. validar upgrade em PostgreSQL fresh;
5. validar downgrade somente quando a semântica for segura;
6. executar `alembic check` no banco fresh e no canônico;
7. provar que as tabelas externas do Trading V2 não aparecem nas operações.

Não usar `Base.metadata.create_all()` no runtime e não criar um segundo
`Base`/engine para contornar migrations.
