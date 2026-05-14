# FinanceOS — ERP financeiro inteligente premium

FinanceOS é um ERP financeiro inteligente para controle de despesas, receitas, contas, cartões, orçamento, metas, investimentos e diagnóstico financeiro em uma experiência SaaS premium.

O frontend oficial agora é React + Vite + TypeScript em `frontend/`. O Streamlit foi preservado apenas como admin legado/operação técnica.

## O que o produto resolve

- Centraliza vida financeira em uma única plataforma.
- Conecta gastos reais com orçamento e metas.
- Calcula saldo mensal, sobra disponível e valor sugerido para investir.
- Entrega diagnóstico financeiro simples para usuário comum.
- Mantém módulos avançados de investimentos, ranking, backtest, ML, jobs e orquestração como diferenciais de bastidor.

## Stack

- Frontend: React, Vite, TypeScript, React Router, TanStack Query, Axios, Recharts, CSS premium responsivo.
- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis.
- Operacional: Celery, MLflow, Docker Compose.
- Admin legado: Streamlit opcional.

## Arquitetura

```text
frontend/                 # frontend principal SaaS React
backend/app/main.py        # API FastAPI
backend/app/erp/           # ERP financeiro premium
backend/app/financial/     # diagnóstico e consultor financeiro existente
backend/app/market/        # mercado, ranking e oportunidades
backend/app/backtest/      # backtests
legacy_streamlit/          # Streamlit legado/admin opcional
```

## Rodar com Docker

```bash
docker compose up --build
```

Acessos:

- Frontend React: http://localhost:3000
- Backend FastAPI: http://localhost:8000
- Healthcheck: http://localhost:8000/health
- Admin Streamlit opcional: `docker compose --profile admin up admin_streamlit`

## Rodar localmente

Backend:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Variáveis principais

Use `.env.example` como base:

```env
FINANCEOS_ENV=development
DATABASE_URL=postgresql+asyncpg://financeos:financeos@postgres:5432/financeos
SYNC_DATABASE_URL=postgresql+psycopg2://financeos:financeos@postgres:5432/financeos
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

## Endpoints SaaS principais

- `/api/auth/login`
- `/api/auth/register`
- `/api/me`
- `/api/dashboard`
- `/api/expenses`
- `/api/incomes`
- `/api/accounts`
- `/api/cards`
- `/api/budgets`
- `/api/goals`
- `/api/financial-diagnosis`
- `/api/investments`
- `/api/portfolio`
- `/api/alerts`
- `/api/plans`
- `/api/health`

## Validação

```bash
python -m compileall .
python scripts/production_readiness_check.py
cd frontend && npm install && npm run build
docker compose config
```

## Aviso legal

O FinanceOS é uma plataforma analítica, educacional e de apoio à decisão. Não é recomendação financeira, consultoria de investimentos, corretora, banco ou instituição regulada.

---

## Ultra Premium UX Patch

O frontend oficial do FinanceOS é React/Vite com TypeScript. Este patch adicionou uma camada de design system premium, componentes reutilizáveis, dark mode refinado, responsividade, lazy loading e melhorias visuais nas telas principais do ERP financeiro.

Telas refinadas:
- Login
- Onboarding
- Dashboard Financeiro
- Despesas
- Orçamento
- Metas/CRUDs financeiros
- Diagnóstico Financeiro
- Investimentos/Carteira/Alertas
- Planos
- Landing page

Comandos principais:

```bash
cd frontend
npm install
npm run build
npm run dev
```

Backend:

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker compose up --build
```

---

## Startup Grade UX Final

Este pacote posiciona o FinanceOS como um ERP financeiro inteligente premium com frontend oficial em React/Vite. O foco do último patch foi polish visual, branding, motion, onboarding, mobile polish, charts premium e percepção de produto SaaS moderno.

### Rodar frontend
```bash
cd frontend
npm install
npm run dev
```

### Build frontend
```bash
cd frontend
npm run build
npm run lint
```

### Rodar backend
```bash
alembic upgrade head
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker
```bash
docker compose up --build
```

O Streamlit permanece como ferramenta legado/admin. O frontend principal do produto é React.

---

## Production / SaaS Ready

Este ZIP inclui patch incremental de produção com:

- Docker Compose de produção (`docker-compose.production.yml`)
- `.env.production.example`
- healthcheck `/health` e readiness `/ready`
- Sentry opcional no frontend/backend
- PostHog opcional
- Stripe-ready para Free/Pro/Premium
- demo pública em `/demo`
- Nginx para frontend SPA e proxy
- documentação em `docs/DEPLOY_PRODUCTION.md`
- apresentação de portfólio em `docs/PORTFOLIO_PRESENTATION.md`

### Rodar produção local/VPS

```bash
cp .env.production.example .env.production
# edite secrets e URLs
./scripts/deploy/start_production.sh
```

### Validação

```bash
python -m compileall backend services db scripts
docker compose -f docker-compose.production.yml config
cd frontend && npm install && npm run build && npm run lint
```

## Backend Enterprise Multi-Tenant

O Vinance agora possui fundação backend SaaS enterprise-ready por organização:

- isolamento por `organization_id`
- RBAC com roles `owner`, `admin`, `finance_manager`, `analyst`, `member`, `viewer`
- dependency FastAPI `require_permission("permission")`
- audit logs por organização
- billing por organização com planos `free`, `pro`, `premium`, `enterprise`
- limites centralizados por plano
- refresh token rotation com hash de tokens
- sessões, reset de senha e verificação de email preparados
- health/readiness/liveness/metrics
- CI com compile, testes, frontend build e validação Docker

Documentação técnica:

- `docs/ENTERPRISE_BACKEND.md`
- `docs/MULTI_TENANCY.md`
- `docs/RBAC.md`
- `docs/SECURITY.md`
- `docs/BILLING_LIMITS.md`
- `docs/AUDIT_LOGS.md`
- `docs/OPERATIONS.md`

### Comandos backend

```bash
python -m compileall .
pytest
alembic upgrade head
```

### Comandos Docker

```bash
docker compose config
docker compose -f docker-compose.production.yml config
```

## Enterprise Backend V2 — Multi-tenant

O backend enterprise do Vinance usa o modelo oficial:

- `organizations`
- `users`
- `organization_members`
- `roles`
- `permissions`
- `subscriptions`
- `tenant_settings`

O modelo legado `tenants` não é mais a fonte principal de autenticação/billing. A autenticação, RBAC e billing usam `organizations` como tenant oficial.

### Segurança e isolamento

- Todas as rotas financeiras principais filtram dados por `organization_id`.
- Permissões são aplicadas com `require_permission("permission.name")`.
- Audit logs registram ações sensíveis com `organization_id`, `user_id` e `request_id`.
- Plan limits são validados no backend antes de criar recursos limitados.

### Validação local

```bash
python -m compileall .
pytest -q tests
alembic upgrade head
docker compose config
docker compose -f docker-compose.production.yml config
cd frontend && npm install && npm run build
```

## Intelligent Investing — ERP + Backtest + ML Contextual

O Vinance agora inclui uma camada backend de inteligência financeira personalizada. O objetivo é transformar os dados do ERP financeiro em recomendações simples para planejamento de investimentos, sem exigir que o usuário entenda métricas quantitativas.

### O que o motor faz

- calcula quanto o usuário pode investir com segurança;
- sugere alocação percentual por classe: ações, FIIs, ETFs, BDRs, cripto, renda fixa/CDI e caixa/reserva;
- executa simulação/backtest personalizado com aporte mensal e cenários;
- ranqueia ativos por qualidade e aderência ao perfil, sem prometer previsão de preço;
- gera recomendação final com explicação humana, risco, meta e benchmarks.

### Endpoints principais

- `POST /api/intelligence/profile`
- `GET /api/intelligence/profile`
- `GET /api/intelligence/capacity`
- `GET /api/intelligence/allocation`
- `GET /api/intelligence/backtest`
- `POST /api/intelligence/asset-scoring`
- `POST /api/intelligence/recommendation`

### Disclaimer financeiro

O Vinance fornece simulações e análises educacionais baseadas em dados históricos e modelos estatísticos. Isso não constitui recomendação financeira.

Documentação complementar:

- `docs/INTELLIGENT_INVESTING.md`
- `docs/BACKTEST_ENGINE.md`
- `docs/ML_SCORING.md`
- `docs/FINANCIAL_PROFILES.md`
- `docs/RECOMMENDATION_ENGINE.md`


## Inteligência Quantitativa Personalizada

O Vinance evoluiu para um assistente financeiro inteligente: usa perfil financeiro, metas, capacidade de aporte, portfolio engine, backtest avançado, ML contextual, cenários e risk engine para traduzir análises quantitativas em recomendações simples.

A proposta não é day trade nem promessa de rentabilidade. O sistema usa modelos educacionais para apoiar planejamento: quanto aportar, risco estimado, chance de atingir meta, cenários e explicações humanas.

Documentação complementar: `docs/GOALS_ENGINE.md`, `docs/ADVANCED_BACKTEST.md`, `docs/PORTFOLIO_ENGINE.md`, `docs/ML_CONTEXTUAL.md`, `docs/RISK_ENGINE.md`, `docs/SCENARIO_SIMULATION.md` e `docs/HUMANIZED_RECOMMENDATIONS.md`.

> Disclaimer: O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.


## Fluxo financeiro principal

O Vinance agora calcula automaticamente o modelo financeiro ideal antes de sugerir investimentos. O fluxo oficial é: renda cadastrada, despesas e dívidas, diagnóstico financeiro, recomendação do modelo mensal, plano de ação e somente depois investimentos com ML/backtest.

A tela **Meu Plano Financeiro** usa o `BudgetModelAdvisorService` para escolher entre Recuperação Financeira, Base Zero, 70/20/10, 60/30/10, 50/30/20 ou Personalizado. As recomendações são educativas e não constituem recomendação financeira.


## Vinance Financial Coach

O Vinance evoluiu para um assistente financeiro inteligente e contínuo. O fluxo principal agora acompanha o usuário além do diagnóstico inicial:

1. entende renda, despesas, dívidas, reserva e metas;
2. recomenda automaticamente o modelo financeiro ideal;
3. calcula score de saúde financeira;
4. identifica a fase atual da jornada financeira;
5. adapta o modelo conforme o usuário melhora ou piora;
6. gera coaching contextual, alertas e próximos passos;
7. projeta cenários pessimista, base e otimista;
8. ajusta a relação com investimentos conforme a capacidade financeira.

### Serviços adicionados

- `financial_health_engine.py`
- `adaptive_budget_model_service.py`
- `financial_coaching_service.py`
- `behavioral_finance_service.py`
- `financial_forecast_service.py`
- `financial_timeline_service.py`

### Endpoint principal

`GET /api/intelligence/financial-coach/dashboard`

Retorna score, fase financeira, modelo adaptativo, coaching, alertas, forecast, timeline e próximo passo recomendado.

### Disclaimer

O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.


## AI Financial Advisor Evolution

O Vinance agora possui uma camada evolutiva de advisor financeiro:

- Memória financeira por organização e usuário
- Coaching contextual avançado
- Inteligência comportamental
- Metas dinâmicas
- Forecast financeiro avançado
- Advisor para decisões como quitar dívida vs investir
- Marcos de evolução financeira premium
- Comunicação humanizada e não técnica

Endpoint principal: `GET /api/intelligence/ai-financial-advisor`.

Disclaimer: o Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.


## Advisor conversacional seguro

O Vinance agora possui um advisor financeiro conversacional baseado nos dados reais do ERP: receitas, despesas, orçamento, metas, reserva, investimentos, forecast, memória financeira e comportamento. O fluxo preserva o isolamento multi-tenant por `organization_id` e `user_id`.

Endpoints principais:

- `GET /api/intelligence/advisor-context`
- `POST /api/intelligence/advisor/chat`
- `GET /api/intelligence/copilot/events`
- `GET /api/intelligence/user-learning-profile`
- `GET /api/intelligence/conversational-advisor/dashboard`

O advisor não promete retorno, não emite ordem de compra/venda e prioriza organização financeira quando a saúde do usuário está crítica.


## Vinance AI Copilot

O Vinance agora possui uma camada de advisor financeiro conversacional e contextual. O usuário pode perguntar livremente sobre orçamento, dívidas, metas, investimentos, carteira, capacidade de aporte e próximos passos. O motor `financial_ai_orchestrator.py` consolida dados reais do ERP, memória financeira, comportamento, forecast, metas e alertas antes de responder.

A resposta passa por guardrails financeiros: sem promessa de retorno, sem ordem de compra/venda, sem incentivo a risco incompatível e com disclaimer educacional. O foco é consultoria financeira personalizada e segura, não trading agressivo.


## Advisor Financeiro — Refinamento Pré-Testes

Esta versão adiciona o último refinamento antes da fase de testes reais:

- UX premium do Advisor Financeiro.
- Memória conversacional longa por organização/usuário.
- RAG financeiro interno com fallback semântico local.
- Modo Advisor Premium com diagnóstico, decisão, riscos e alternativas.
- Analytics de IA sem persistir prompt sensível.
- Cache/compactação de contexto para melhorar performance.
- Guardrails antes e depois da resposta.

Documentação relacionada:

- `docs/ADVISOR_PREMIUM.md`
- `docs/CONVERSATIONAL_MEMORY.md`
- `docs/FINANCIAL_RAG_ENGINE.md`
- `docs/PROACTIVE_COPILOT.md`
- `docs/AI_ANALYTICS.md`
- `docs/AI_SAFETY.md`
- `docs/VALIDATION_CHECKLIST.md`

Disclaimer: o Vinance fornece análises educacionais baseadas em dados e simulações. Isso não constitui recomendação financeira individualizada.
