# Fase 0 — Saneamento Arquitetural do Vinance v2

## 1. Objetivo

Esta fase prepara o projeto legado `financeos_work` para virar o **Vinance v2**, uma plataforma pessoal de inteligência financeira para o mercado brasileiro.

A Fase 0 **não implementa produto**, **não altera regra financeira**, **não cria endpoints**, **não cria migrations** e **não mexe no frontend**. O trabalho aqui é separar o que existe, registrar decisões arquiteturais e criar uma base mínima para a próxima etapa de refatoração.

## 2. Visão geral do estado atual

O ZIP base contém uma evolução acumulada do FinanceOS, com várias camadas misturadas:

- `backend/`: backend FastAPI mais próximo da base reaproveitável.
- `frontend/`: frontend React/Vite existente, preservado para consulta, mas não tratado como frontend definitivo do Vinance v2.
- `legacy_streamlit/`: aplicação Streamlit antiga, útil apenas como referência histórica.
- `admin_streamlit/`: camada administrativa legada, não priorizada para o Vinance v2.
- `alembic/` e `backend/alembic/`: migrations acumuladas em mais de uma árvore.
- `data/catalog_fallback/`: catálogos locais/fallback de ativos, potencialmente reaproveitáveis após validação.
- `services/`, `workers/`, `scripts/`: serviços, jobs e automações criados ao longo dos patches anteriores.
- `backend/app/financial`, `backend/app/market`, `backend/app/intelligence`: módulos com lógica importante, mas ainda acoplados ao desenho antigo.
- `backend/app/backtest`, `backend/app/investment`, `backend/app/decision`, `backend/app/analytics`: módulos que devem ser auditados antes de qualquer reaproveitamento.

O principal problema arquitetural é que o projeto mistura produto final, experimentos, legado, rotas operacionais, scripts de ML, jobs, frontend antigo, Streamlit e migrations históricas sem uma fronteira clara entre módulos.

## 3. O que será reaproveitado

Reaproveitamento condicionado a revisão manual na Fase 1 ou posterior:

| Área | Caminhos prováveis | Decisão |
|---|---|---|
| Backend FastAPI | `backend/app/main.py`, `backend/app/core`, `backend/app/auth` | Reaproveitar parcialmente após isolamento do core. |
| Autenticação | `backend/app/auth` | Reaproveitar se estiver desacoplada de planos/demo/legado. |
| Financeiro | `backend/app/financial`, partes de `services/financial_*` | Reaproveitar a lógica validada, mas refatorar para módulo limpo. |
| Mercado | `backend/app/market`, `data/catalog_fallback`, scripts de catálogo | Reaproveitar apenas depois de validar fontes, schema e contratos. |
| Inteligência | `backend/app/intelligence` e serviços relacionados | Reaproveitar conceitos, não necessariamente a implementação atual. |
| Celery/Redis | `workers/`, variáveis de ambiente e compose | Reaproveitar como base operacional mínima. |
| Testes | `backend/tests`, `tests` | Reaproveitar testes úteis após reorganizar import paths. |
| Documentação histórica | `docs/` e relatórios `PATCH_*` | Preservar como referência, mas não tratar como arquitetura atual. |

## 4. O que será descartado ou isolado

Nada foi removido nesta fase. Os itens abaixo foram apenas classificados:

| Área | Caminho | Decisão |
|---|---|---|
| Streamlit legado | `legacy_streamlit/` | Não reutilizável como produto final. Preservar apenas para consulta temporária. |
| Admin Streamlit | `admin_streamlit/` | Fora da base operacional inicial do Vinance v2. |
| Frontend atual | `frontend/` | Preservado, mas marcado como descartável para a nova identidade do Vinance v2. |
| Migrations antigas | `alembic/`, `backend/alembic/` | Legado. Não criar migration nova até o Core Backend estar definido. |
| ML operacional | scripts `ml_*`, serviços `ml_*`, backtests | Fora da Fase 0 e da Fase 1 inicial. Manter congelado. |
| Advisor IA | módulos/serviços de advisor/copilot/IA | Fora da Fase 0. Não usar Ollama. Decisão futura: Groq. |
| Billing/Enterprise | `backend/app/billing`, `backend/app/enterprise` | Não prioritário para produto pessoal v2. Isolar. |

## 5. O que precisa ser refatorado

1. **Core Backend**
   - Separar configuração, banco, segurança, logging, exceptions e healthcheck.
   - Definir uma única origem de configuração.
   - Padronizar `DATABASE_URL`, Redis e Celery.

2. **API v1**
   - Criar roteamento claro em `backend/app/api/v1`.
   - Não migrar rotas antigas automaticamente.
   - Definir contratos antes de mover endpoints.

3. **Financial**
   - Isolar entidades financeiras pessoais: salário, despesas, orçamento, capacidade mensal de investimento e score.
   - Não alterar cálculo financeiro nesta fase.

4. **Market**
   - Separar catálogos, providers externos e cache.
   - Evitar dependência direta de scripts soltos.

5. **Intelligence**
   - Separar motor determinístico de recomendação/orçamento da futura camada de IA.
   - Não misturar ML/advisor com regra financeira base.

6. **Advisor**
   - Criar fronteira de módulo, mas manter vazio nesta fase.
   - Futuramente integrar Groq, sem Ollama.

7. **Migrations**
   - Congelar migrations antigas como legado.
   - Criar nova estratégia somente depois do modelo canônico da Fase 1.

## 6. Estrutura alvo documentada

Estrutura preparada/documentada para o Vinance v2:

```text
backend/
  app/
    core/             # configuração, banco, segurança, logging, exceptions
    auth/             # autenticação e sessão
    financial/        # orçamento, despesas, score financeiro e capacidade de investimento
    market/           # ativos, catálogos, preços, dados de mercado
    intelligence/     # regras determinísticas e motores de recomendação
    advisor/          # camada futura de IA/advisor, inicialmente vazia
    api/
      v1/             # roteamento público versionado
  tests/              # testes do backend v2

data/
  catalogs/           # catálogos versionados e controlados

scripts/              # scripts operacionais revisados
```

## 7. Dependências entre módulos

```text
core
 ├── auth
 ├── financial
 ├── market
 ├── intelligence
 └── advisor

api/v1
 ├── auth
 ├── financial
 ├── market
 ├── intelligence
 └── advisor

intelligence
 ├── financial
 └── market

advisor
 ├── financial
 ├── market
 └── intelligence
```

Regras de dependência:

- `core` não deve depender de módulo de negócio.
- `financial` não deve depender de `advisor`.
- `market` não deve depender de `advisor`.
- `intelligence` pode consumir `financial` e `market`, mas deve continuar determinística.
- `advisor` deve ser camada superior, consumindo contexto pronto, sem controlar regra financeira.
- `api/v1` deve orquestrar casos de uso, não concentrar regra de negócio.

## 8. Riscos técnicos

| Risco | Impacto | Mitigação |
|---|---|---|
| Duas árvores de migrations | Alto | Congelar migrations antigas e definir modelo canônico antes de migrar banco. |
| Frontend antigo influenciar arquitetura nova | Médio/alto | Preservar frontend apenas como referência visual/funcional temporária. |
| Streamlit misturado ao produto | Médio | Marcar Streamlit como legado não reutilizável. |
| Scripts com lógica crítica fora do backend | Alto | Auditar scripts antes de mover qualquer regra. |
| Serviços globais em `services/` | Alto | Reclassificar serviço por domínio antes de importar no v2. |
| ML/advisor contaminar core financeiro | Alto | Manter ML/advisor congelados até depois do Core Backend e Financial. |
| Providers externos frágeis | Médio/alto | Não mexer em providers na Fase 0; criar contratos depois. |
| Documentação histórica contraditória | Médio | Usar este relatório como referência da transição para Vinance v2. |

## 9. Infraestrutura mínima definida

A infraestrutura mínima da Fase 0 passa a considerar apenas:

- `backend`
- `postgres`
- `redis`
- `celery_worker`
- `celery_beat`

Itens removidos do compose operacional mínimo:

- frontend como serviço obrigatório
- Streamlit admin/legado
- MLflow
- serviços experimentais de produção antiga

Essa decisão não apaga os arquivos existentes. Apenas reduz o ambiente base para a refatoração segura.

## 10. Ordem recomendada das próximas fases

### Fase 1 — Core Backend

- Consolidar configuração em `backend/app/core`.
- Definir conexão com PostgreSQL e Redis.
- Definir healthcheck mínimo.
- Definir estrutura de exceptions/logging.
- Preparar base de testes.
- Não criar regra financeira nova ainda.

### Fase 2 — Auth e Usuário

- Revisar autenticação existente.
- Separar usuário, sessão e segurança.
- Garantir compatibilidade com PostgreSQL.

### Fase 3 — Financial Engine

- Isolar orçamento automático.
- Isolar despesas, receitas, capacidade de investimento e score.
- Validar regras financeiras antes de IA.

### Fase 4 — Market Catalogs

- Reorganizar catálogos brasileiros por classe de ativo.
- Separar FIIs, ações, ETFs, BDRs, cripto e renda fixa.
- Definir TTL e estratégia de histórico.

### Fase 5 — Intelligence Determinística

- Recomendações por classe de ativo.
- Regras sem ML e sem advisor IA.

### Fase 6 — Advisor IA

- Integrar Groq sobre contexto já calculado.
- Não usar Ollama.
- Não permitir que IA substitua regra financeira determinística.

### Fase 7 — Frontend novo

- Descartar frontend React antigo como base de produto.
- Criar identidade visual própria do Vinance v2.

## 11. Checklist final da Fase 0

- [x] Estrutura limpa alvo documentada.
- [x] Pastas mínimas preparadas quando ausentes.
- [x] Legado identificado.
- [x] Nada crítico removido sem registro.
- [x] Frontend preservado, mas marcado como descartável.
- [x] Streamlit legado marcado como não reutilizável.
- [x] Migrations antigas marcadas como legado.
- [x] Infraestrutura mínima reduzida para backend, Postgres, Redis, Celery worker e Celery beat.
- [x] Próxima fase definida como Core Backend.

## 12. Pendências para Fase 1

- Definir ponto de entrada canônico do backend v2.
- Auditar `backend/app/main.py` antes de qualquer alteração.
- Escolher uma única estratégia de configuração.
- Validar dependências reais do `requirements.txt`.
- Definir estratégia de banco antes de novas migrations.
- Criar testes mínimos de saúde/importação do core.
- Mapear quais serviços de `services/` pertencem a `financial`, `market`, `intelligence` ou devem ser descartados.
