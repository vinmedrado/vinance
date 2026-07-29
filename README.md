# Vinance

Sistema operacional financeiro com IA, ERP, orcamento, investimentos e copiloto financeiro inteligente.

O frontend oficial e React + Vite + TypeScript em `frontend/`. O Streamlit foi preservado apenas como admin legado e apoio operacional.

## Visao geral

Vinance organiza dados financeiros pessoais e transforma esses dados em diagnostico, planejamento, alertas, recomendacoes e leitura executiva da carteira.

## Problema que resolve

- Controle financeiro disperso entre planilhas e aplicativos isolados.
- Dificuldade para entender capacidade real de aporte.
- Falta de um fluxo unico entre orcamento, metas e investimentos.
- Necessidade de contextualizar a informacao para o usuario final.

## Arquitetura

```text
frontend/        frontend principal SaaS
backend/app/     API FastAPI
backend/app/erp/ ERP financeiro
backend/app/financial/ diagnostico e consultoria
backend/app/market/ mercado, ranking e oportunidades
backend/app/backtest/ backtests
legacy_streamlit/ admin legado
```

## Screenshots

![Portfolio screenshot](https://raw.githubusercontent.com/vinmedrado/portfolio/main/images/vinance.png)

## Funcionalidades

- Controle de despesas, receitas, contas e cartoes.
- Orcamento e metas financeiras.
- Diagnostico financeiro.
- Carteira e investimentos.
- Advisor com IA e guardrails.
- Multi-tenancy com isolamento por organizacao.
- Auditoria e controle de acesso.

## Tecnologias

Python, FastAPI, PostgreSQL, Redis, Celery, React, TypeScript, Vite, Docker, SQLAlchemy, Alembic.

## Como executar

### Docker

```bash
docker compose up --build
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
alembic upgrade head
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## Estrutura do projeto

```text
frontend/       frontend principal
backend/        API e dominio
legacy_streamlit/ legado administrativo
docs/           documentacao tecnica
tests/          testes
scripts/        scripts operacionais
services/       regras de negocio
workers/        jobs
```

## Roadmap

- Reduzir redundancias de documentacao antiga.
- Consolidar a experiencia premium do frontend.
- Refinar a narrativa da area de investimentos e advisor.

## Licenca

TODO.
