# Arquitetura do FinanceOS

## Visão geral

O FinanceOS é organizado como uma plataforma modular com backend FastAPI, frontend React/Vite, serviços de domínio, pipelines de dados, backtests, ranking de ativos e módulos de inteligência.

A refatoração preserva a compatibilidade dos imports existentes e evita reescrever regras de negócio. A pasta `legacy_streamlit/` preserva a interface Streamlit histórica apenas como admin legado; `frontend/` é o produto SaaS oficial.

## Camadas

### Interface

- `legacy_streamlit/main_streamlit.py`: entrada principal do Streamlit.
- `legacy_streamlit/pages/`: páginas históricas do admin Streamlit.

### Backend

- `backend/app/main.py`: aplicação FastAPI.
- `backend/app/*`: módulos de domínio, autenticação, billing, backtest, mercado, dados e serviços internos.

### Serviços

- `services/`: serviços usados por páginas, scripts e fluxos operacionais.
- Inclui automações, jobs, ranking final, ML, alertas, portfólio e UI helpers.

### Dados e persistência

- `db/`: conexão, compatibilidade SQL e modelos legados.
- `alembic/`: migrations.
- `data/`: dados locais, catálogos e bases de apoio.

### Scripts

- `scripts/`: ingestão, sincronização, validação, backtest, ML, relatórios e healthchecks.

## Fluxo de dados

1. Scripts e pipelines coletam dados de mercado, catálogos, dividendos, índices e indicadores.
2. Os dados são persistidos em banco local ou PostgreSQL.
3. Serviços calculam métricas, qualidade, scores e rankings.
4. O frontend React/Vite entrega a experiência pública; o Streamlit legado pode acionar rotinas operacionais internas quando usado localmente.
5. O backend FastAPI expõe rotas e integrações.
6. Jobs assíncronos podem ser executados via Celery/Redis.

## Ranking final

O ranking final combina métricas de retorno, risco, liquidez, qualidade de dados, sinais analíticos e resultados de backtest. A camada calibrada evita comparação global inadequada entre mercados diferentes, favorecendo normalização por classe de ativo.

## Backtest

O módulo de backtest executa estratégias, rebalanceamentos, métricas de performance e comparação de resultados. A arquitetura preserva estratégias existentes e permite evolução incremental sem alterar o núcleo original.

## Serviços principais

- `final_ranking_service.py`: ranking final e calibração.
- `background_jobs.py` e `job_executor.py`: fila e execução de jobs.
- `financeos_orchestrator.py`: orquestração geral.
- `ml_*`: dataset, treino, predição e registry de modelos.
- `asset_*`: catálogo, qualidade, descoberta e ranking de ativos.
- `portfolio_service.py` e `alert_engine.py`: carteira e alertas.

## Separação por camadas

A separação recomendada é:

- Core/configuração: `app/core` e `backend/app/core`
- Modelos: `app/models`, `backend/app/*/models.py` e `db/`
- Schemas: `app/schemas` e `backend/app/*/schemas.py`
- Services: `services/` e `backend/app/*/services`
- Routes: `backend/app/*/routers` e `app/routes` para evolução futura
- Repositories: `backend/app/*/repositories`, `app/repositories` e `db/`
- Utils: `app/utils`, `services/ui_helpers.py` e utilitários internos
