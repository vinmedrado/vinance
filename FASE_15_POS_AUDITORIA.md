# Fase 15 — Correções Pós-Auditoria

## Objetivo
Corrigir pontos estruturais apontados na auditoria antes da criação de providers reais, features de ML ou novas tabelas analíticas.

## Alterações executadas
- Pasta legada `db/` arquivada em `_archived/fase15_legacy_db/db/`.
- `requirements.txt` atualizado com dependências futuras controladas para dados/quant/providers: `yfinance`, `pandas`, `numpy`, `scikit-learn`, `xgboost`, `beautifulsoup4` e `tenacity`.
- `backend/alembic/env.py` passou a importar explicitamente os models ativos de mercado para o `autogenerate` reconhecer as tabelas existentes.
- `backend/app/core/celery.py` ajustado para usar `crontab` nos jobs programados já existentes.
- `frontend/package.json` deixou de usar `latest` e passou a ter versões fixadas compatíveis.

## O que não foi alterado
- Nenhum provider externo novo foi criado.
- Nenhum arquivo `brapi.py`, `coingecko.py` ou `statusinvest.py` foi criado.
- Nenhum scraping foi implementado.
- Nenhuma feature de ML ou tabela `_ml_features` foi criada.
- Nenhuma regra financeira, market, intelligence, advisor ou visual de frontend foi alterado.

## Providers e ML
Brapi, CoinGecko, StatusInvest e novas features de ML permanecem fora desta fase e devem ser tratados em fases futuras específicas, com escopo próprio.

## Validações executadas
- `python -m compileall backend/app scripts workers`
- `npm install`
- `npm run build`

## Riscos remanescentes
- Dependências de dados e ML foram adicionadas, mas ainda não são utilizadas por providers reais nesta fase.
- A geração de migrations via Alembic deve ser feita apenas quando uma fase de schema for aprovada.
- Jobs Celery dependem de Redis e worker/beat configurados corretamente no ambiente de execução.

## Estado final
A base fica mais segura contra acoplamento legado, com dependências preparadas, Alembic mais confiável para autogenerate e agenda Celery mais explícita para rotinas recorrentes.
