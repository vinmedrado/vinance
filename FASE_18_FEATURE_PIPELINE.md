# Fase 18 — Intelligence Feature Pipeline Base

## Objetivo
Criar a primeira base quantitativa real do Vinance v2 para alimentar a camada de intelligence sem treinar modelos de ML, sem backtest completo, sem alterar frontend, sem alterar advisor e sem mexer nos providers aprovados.

## Arquivos criados

### Migrations
- `backend/alembic/versions/0006_create_ml_features_tables.py`

### Models SQLAlchemy
- `backend/app/intelligence/models/__init__.py`
- `backend/app/intelligence/models/_base_features.py`
- `backend/app/intelligence/models/fii_features.py`
- `backend/app/intelligence/models/acoes_features.py`
- `backend/app/intelligence/models/etf_features.py`
- `backend/app/intelligence/models/bdr_features.py`
- `backend/app/intelligence/models/cripto_features.py`

### Feature pipeline
- `backend/app/intelligence/feature_pipeline/__init__.py`
- `backend/app/intelligence/feature_pipeline/common.py`
- `backend/app/intelligence/feature_pipeline/fii_features.py`
- `backend/app/intelligence/feature_pipeline/acoes_features.py`
- `backend/app/intelligence/feature_pipeline/etf_features.py`
- `backend/app/intelligence/feature_pipeline/bdr_features.py`
- `backend/app/intelligence/feature_pipeline/cripto_features.py`

### Scoring e service
- `backend/app/intelligence/feature_scoring.py`
- `backend/app/intelligence/feature_service.py`

### Scheduler
- `backend/app/intelligence/scheduler/__init__.py`
- `backend/app/intelligence/scheduler/tasks.py`

### Testes
- `backend/tests/test_feature_pipeline_phase18.py`

## Arquivos alterados
- `backend/alembic/env.py`: importa os novos models de features para autogenerate.
- `backend/app/core/celery.py`: inclui scheduler de intelligence e agenda diária 23h30.
- `backend/app/intelligence/router.py`: adiciona endpoint autenticado `GET /api/v1/intelligence/features/status`.
- `backend/app/intelligence/service.py`: recommendations priorizam `score_final` das features quando existem e mantêm fallback heurístico quando vazias.

## Tabelas criadas
- `fii_ml_features`
- `acoes_ml_features`
- `etf_ml_features`
- `bdr_ml_features`
- `cripto_ml_features`

As tabelas possuem constraints únicas por `ticker + date`, exceto cripto com `coin_id + date`, e índices em `ticker/date` e `score_final`.

## Features por mercado

### FIIs
- `dy_trend_3m`
- `pvp_zscore`
- `vacancia_delta`
- `momentum_30d`
- `momentum_90d`
- `volatilidade_30d`
- `retorno_vs_ifix`
- `score_final`

### Ações
- `pl_zscore`
- `roe_trend_3m`
- `momentum_30d`
- `momentum_90d`
- `momentum_252d`
- `volatilidade_30d`
- `volatilidade_90d`
- `retorno_vs_ibov`
- `volume_anomaly`
- `score_final`

### ETFs
- `taxa_adm_rank`
- `tracking_score`
- `momentum_30d`
- `momentum_90d`
- `volatilidade_30d`
- `retorno_vs_benchmark`
- `score_final`

### BDRs
- `cambio_trend_30d`
- `momentum_30d`
- `momentum_90d`
- `volatilidade_30d`
- `retorno_vs_spy`
- `liquidez_score`
- `score_final`

### Cripto
- `volatilidade_7d`
- `volatilidade_30d`
- `correlacao_btc_30d`
- `momentum_7d`
- `momentum_30d`
- `momentum_90d`
- `volume_anomaly`
- `fear_greed_score`
- `score_final`

## Metodologia
O pipeline usa dados reais já persistidos nas tabelas de preços e fundamentos. Quando histórico ou fundamentos estão ausentes, a feature retorna `None` e o cálculo não quebra. O `score_final` é heurístico e usa apenas campos disponíveis.

## Pesos heurísticos
- FIIs: dividendos, valuation relativo, vacância, momentum, volatilidade e retorno relativo.
- Ações: valuation relativo, qualidade, momentum, volatilidade, retorno relativo e liquidez.
- ETFs: custo, tracking, momentum, volatilidade e retorno relativo.
- BDRs: risco cambial, momentum, volatilidade, retorno relativo e liquidez.
- Cripto: volatilidade, momentum, correlação, volume e indicador de sentimento quando disponível.

Dados ausentes recebem peso neutro reduzido. Isso evita inventar dados e evita que ativos sem histórico sejam premiados indevidamente.

## Fallback
A recommendation engine agora segue esta prioridade:
1. Se houver `score_final` em `*_ml_features`, usa o score quantitativo heurístico.
2. Se não houver features, mantém o ranking heurístico por fundamentos da Fase 6.

A metodologia da resposta informa explicitamente se usou “features quantitativas disponíveis” ou “fallback heurístico por fundamentos”.

## Tasks Celery criadas
- `intelligence.compute_daily_fii_features`
- `intelligence.compute_daily_acoes_features`
- `intelligence.compute_daily_etf_features`
- `intelligence.compute_daily_bdr_features`
- `intelligence.compute_daily_cripto_features`
- `intelligence.compute_all_market_features`

Beat configurado para rodar diariamente às 23h30 em `America/Sao_Paulo`, após as coletas de mercado.

## Endpoint interno
- `GET /api/v1/intelligence/features/status`

Retorna última data calculada e quantidade de features por mercado. O endpoint exige autenticação e não expõe treino de ML.

## Por que ML ainda não foi treinado
Esta fase cria a base de dados e o pipeline de features. Treinar XGBoost, LSTM, Prophet ou qualquer modelo antes de validar consistência, volume histórico e qualidade das features criaria risco de overfitting e falsas recomendações. O score desta fase é heurístico e documentado.

## Riscos remanescentes
- Algumas features relativas dependem de benchmarks que ainda precisam estar consistentemente no banco.
- BDR e ETF ainda podem ter pouca profundidade de fundamentos dependendo dos providers futuros.
- Cripto ainda não possui `fear_greed_score` real integrado.
- A qualidade do ranking depende da cobertura de preços/fundamentos coletados.

## Preparação para Fase 19
A Fase 19 poderá evoluir para validação histórica, dataset supervisionado, backtest controlado ou preparação de treinamento, mas ainda deverá respeitar a separação entre feature engineering e recomendação definitiva.

## Validação executada
- `python -m compileall backend/app scripts workers`: executado.
- `pytest`: tentado; no sandbox pode ser bloqueado por dependências externas ausentes.
- `alembic upgrade head`, backend startup, worker/beat startup: dependem do ambiente Docker/PostgreSQL/Redis do projeto.
