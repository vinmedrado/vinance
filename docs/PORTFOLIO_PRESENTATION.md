# FinanceOS — Portfolio Presentation

## Visão do produto

FinanceOS é um ERP financeiro inteligente com experiência premium para controle de despesas, orçamento, metas, diagnóstico financeiro, investimentos, automações, backtests e arquitetura SaaS-ready.

## Diferenciais

- Frontend React/Vite com UI premium e rotas protegidas.
- Backend FastAPI modular.
- PostgreSQL, Redis, workers e estrutura de produção.
- Demo pública isolada para recrutadores/clientes.
- Analytics desacoplado com PostHog opcional.
- Observabilidade com Sentry opcional no frontend e backend.
- Billing ready com estrutura Free, Pro e Premium.
- Documentação de deploy para Docker, VPS, Render e Railway.

## Stack

React, Vite, TypeScript, FastAPI, SQLAlchemy, PostgreSQL, Redis, Docker, Nginx, Sentry, PostHog, Stripe-ready, Celery e ML/backtesting.

## Arquitetura

```text
Usuário -> Nginx -> Frontend React
                 -> Backend FastAPI -> PostgreSQL
                                    -> Redis/Workers
                                    -> Sentry/PostHog/Stripe
```

## Funcionalidades

- Login e rotas protegidas.
- Dashboard financeiro.
- Cadastro de despesas, receitas, metas, orçamento e investimentos.
- Diagnóstico financeiro.
- Planos SaaS e feature gating.
- Demo pública premium.
- Healthchecks e readiness checks.

## Screenshots sugeridos

Adicione imagens reais em `docs/screenshots/`:

- landing/dashboard;
- despesas premium;
- orçamento/metas;
- diagnóstico;
- planos;
- demo pública.

## Roadmap

1. Stripe checkout completo em produção.
2. Admin multi-tenant completo.
3. Relatórios PDF premium.
4. API pública versionada.
5. Alertas inteligentes e automações programadas.
