# Onda D — analytics, trading e orquestração legados

## Escopo e decisão arquitetural

A Onda D remove os entry points SQLite de analytics, backtest, catálogo,
pipelines e quant intelligence que não pertenciam ao call graph do FastAPI ou
do Celery oficiais. Nenhum SQL SQLite foi convertido para PostgreSQL. As fontes
canônicas permanecem `backend.app.intelligence`, Recommendation Engine, Celery
e `backend/trading` V2.

Foram aposentados fisicamente:

- `backend/app/analysis`;
- `backend/app/backtest` (stack histórica, distinta de `backend/trading`);
- `backend/app/data_layer` e seus pipelines SQLite;
- os routers antigos em `backend/app/market/routers`;
- `backend/app/quant_intelligence` e a tela QuantLab não roteada;
- os trackers antigos `catalog_pipeline_runs` e `market_data_pipeline_runs`;
- o executor de background que dependia desses trackers.

## Histórico e integridade PostgreSQL

A inspeção foi executada em transação `READ ONLY`. O schema de
`public.backtest_runs` contém `name`, `strategy_version`, timestamps,
`parameters` e `metrics` JSONB. Os sete registros possuem versões
`logistic_v1` ou `logistic_research_v2`, exatamente os contratos gravados pelos
scripts em `backend/trading`. A classificação é `TRADING_V2_HISTORY` e
`HISTORICAL_EXPORT_REQUIRED = NÃO`.

Snapshot anterior às alterações:

| Tabela | Linhas |
| --- | ---: |
| `asset_catalog` | 3.867 |
| `asset_prices` | 50 |
| `asset_scores` | 148.243 |
| `macro_indicators` | 44 |
| `backtest_runs` | 7 |

O valor de `asset_scores` já era 148.243 antes da Onda D; 144.448 era um
snapshot histórico anterior. O gate desta execução exige 148.243 antes e
depois, sem corrigir ou reescrever dados.

## Trading V2 e artifacts

Não houve alteração sob `backend/trading`. Permanecem versionados Feature Store
V2, Target Engine V2, ML Engine V2, Prediction Engine V2, Paper Trading V2,
Backtesting V2, Research V2, Validation V2, History Expansion V2 e Experiment
Campaign V2.

Foram encontrados 632 arquivos locais em
`backend/trading/artifacts/ml_engine_v2`; todos são `TRADING_V2_ARTIFACT`, estão
ignorados pelo Git e foram preservados. Em `data/ml_artifacts` existe somente o
`.gitkeep` versionado, portanto não foi encontrado artifact ML legado real para
exclusão.

## Componentes encaminhados à Onda E

Na conclusão da Onda D, alguns módulos legados ainda permaneciam fisicamente no
worktree porque continham tarefas decoradas ou eram dependências diretas de
scripts locais. O registry real do worker e o call graph do FastAPI confirmaram
que nenhum integrava o runtime oficial. Eles foram encaminhados à Onda E:

- `workers/tasks.py` e os serviços `ml_*` antigos;
- `services/automation_service.py`, `background_jobs.py` e `job_executor.py`;
- `services/financeos_orchestrator.py` e `services/agents`;
- `services/asset_quality_service.py` e `asset_ranking_service.py`;
- `services/intelligence_history_service.py` e `alert_engine.py`;
- scripts de analysis/backtest/catálogo/ML que importavam as stacks aposentadas;
- `services/asset_catalog_db.py`, importadores Excel e utilitários SQLite locais.

Esses itens foram aposentados na Onda E. Nenhum estava no registry real do
worker canônico.

## Garantias

- schema alterado: NÃO;
- migration criada: NÃO;
- dados alterados: NÃO;
- DDL executado no PostgreSQL: NÃO;
- `backend/trading` alterado: NÃO;
- artifacts V2 apagados: NÃO;
- Recommendation Engine alterado: NÃO;
- dependência SQLite/`pg_compat` no runtime moderno: NÃO.
