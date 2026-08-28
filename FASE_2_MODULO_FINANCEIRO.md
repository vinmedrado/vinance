# Fase 2 — Módulo Financeiro

## Status

Fase 2 implementada sobre a Fase 1 aprovada, mantendo o escopo restrito ao núcleo financeiro do Vinance v2.

Não houve avanço para market, catálogo de ativos, ML, advisor IA, providers externos, frontend ou billing.

## Arquivos criados

- `backend/app/financial/models.py`
- `backend/app/financial/schemas.py`
- `backend/app/financial/router.py`
- `backend/app/financial/service.py`
- `backend/app/financial/budget_engine.py`
- `backend/app/financial/scoring.py`
- `backend/alembic/versions/0002_create_financial_tables.py`
- `backend/tests/test_financial_engine.py`
- `backend/tests/test_financial_router.py`
- `FASE_2_MODULO_FINANCEIRO.md`

## Arquivos alterados

- `backend/app/financial/__init__.py`
  - Exporta os modelos oficiais do módulo financeiro.
- `backend/app/api/v1/router.py`
  - Registra o router financeiro em `/api/v1/financial`.
- `backend/app/models.py`
  - Expõe os modelos financeiros junto ao `User` para manter metadata centralizada.
- `backend/alembic/env.py`
  - Importa os modelos financeiros para que o Alembic reconheça a metadata única.

## Migration criada

### `0002_create_financial_tables.py`

Cria exclusivamente as tabelas da Fase 2:

- `incomes`
- `expenses`
- `financial_profiles`

Características:

- `user_id` com FK para `users.id`.
- Índices em `user_id`.
- Índices úteis em datas financeiras:
  - `incomes.received_at`
  - `expenses.due_date`
- Índices operacionais em:
  - `expenses.category`
  - `expenses.is_paid`
- `financial_profiles.user_id` único para garantir um perfil financeiro por usuário.

A migration não altera tabelas fora do escopo financeiro.

## Endpoints implementados

Prefixo autenticado:

`/api/v1/financial`

Endpoints:

- `POST /incomes`
- `GET /incomes`
- `POST /expenses`
- `GET /expenses`
- `POST /profile`
- `GET /profile`
- `GET /diagnosis`

Todos usam o usuário autenticado pelo JWT existente da Fase 1 via `get_current_user`.

## Regras do Budget Engine

Arquivo:

`backend/app/financial/budget_engine.py`

Entrada:

- `monthly_salary`
- `total_expenses_30d`
- `emergency_reserve`
- `has_debt_default`
- `financial_score`

Regras implementadas:

- Proporção calculada por `total_expenses_30d / monthly_salary`.
- Proporção maior que `0.60` define método `80/15/5`.
- Proporção maior que `0.40` define método `70/20/10`.
- Proporção menor ou igual a `0.40` define método `50/30/20`.
- Inadimplência ativa força método `80/15/5`.
- Reserva menor que 3 meses de despesas reduz a capacidade sugerida de investimento e prioriza reserva.
- Score menor que 40 bloqueia risco alto.
- Inadimplência também bloqueia risco alto.

Saída:

- `method`
- `committed_ratio`
- `total_expenses_30d`
- `investment_percentage`
- `investment_capacity`
- `emergency_reserve_priority`
- `high_risk_allowed`
- `explanation`

## Regras do Scoring

Arquivo:

`backend/app/financial/scoring.py`

Critérios implementados:

- Score inicia em 100.
- Penaliza inadimplência.
- Penaliza despesas acima de 60% da renda.
- Penaliza despesas entre 40% e 60% da renda.
- Penaliza reserva de emergência menor que 3 meses de despesas.
- Penaliza capacidade de investimento muito baixa.
- Score é limitado entre 0 e 100.

Níveis:

- `critical`: score menor que 40.
- `attention`: score de 40 a 69.
- `healthy`: score de 70 a 89.
- `excellent`: score de 90 a 100.

## Testes criados

### `backend/tests/test_financial_engine.py`

Cobre:

- Budget `80/15/5` quando proporção é maior que 60%.
- Budget `70/20/10` quando proporção é maior que 40%.
- Budget `50/30/20` quando proporção é menor ou igual a 40%.
- Inadimplência forçando `80/15/5`.
- Score menor que 40 bloqueando risco alto.
- Reserva menor que 3 meses priorizando reserva.
- Score financeiro dentro de 0-100 com penalidades esperadas.

### `backend/tests/test_financial_router.py`

Cobre contratos autenticados dos endpoints financeiros:

- Criação/listagem de receitas.
- Criação/listagem de despesas.
- Criação/consulta de perfil financeiro.
- Diagnóstico financeiro autenticado.

Os testes de router isolam dependências externas para não depender de Postgres/Redis durante `pytest`, mas a lógica real de orçamento e score é testada diretamente.

## Validação executada

Executado com sucesso:

```bash
python -m compileall backend/app workers
pytest
```

Resultado do `pytest`:

```text
13 passed
```

Validação parcial de import/runtime:

```bash
python - <<'PY'
from backend.app.main import app
from backend.app.core.celery import celery_app
print(app.title)
print(celery_app.main)
PY
```

Resultado:

```text
Vinance v2
vinance_v2
```

## Validações dependentes de infraestrutura local

Não foi possível concluir neste ambiente:

- `alembic upgrade head`
- iniciar backend com Postgres/Redis reais
- validar `/health` com banco e Redis ativos
- validar fluxo real `register → login → profile → incomes → expenses → diagnosis` contra containers

Motivo: o ambiente de execução não possui Docker e não há Postgres/Redis ativos com hostname `postgres`/`redis`.

Comando executado:

```bash
alembic upgrade head
```

Resultado: falhou por indisponibilidade de infraestrutura, não por erro de sintaxe da migration. O erro foi resolução/conexão do host `postgres`.

Validação local recomendada após subir containers:

```bash
docker compose up --build
alembic upgrade head
```

Depois validar:

```bash
curl http://localhost:8000/health
```

E o fluxo autenticado:

1. `POST /register`
2. `POST /login`
3. `POST /api/v1/financial/profile`
4. `POST /api/v1/financial/incomes`
5. `POST /api/v1/financial/expenses`
6. `GET /api/v1/financial/diagnosis`

## Decisões arquiteturais

- O módulo financeiro foi criado em `backend/app/financial`, isolado de market, intelligence e advisor.
- Dinheiro usa `Decimal`/`Numeric(14,2)`, evitando `float` para valores financeiros.
- O diagnóstico financeiro não chama IA, API externa, provider, ML ou catálogo de ativos.
- O service filtra sempre por `user_id`, impedindo acesso cruzado entre usuários.
- O perfil financeiro é único por usuário.
- O budget engine e o scoring ficaram como funções puras para facilitar testes e evolução.
- O router financeiro usa autenticação JWT já existente, sem recriar auth.

## Riscos remanescentes

- A migration precisa ser validada em Postgres real via Docker/local.
- O fluxo de ponta a ponta precisa ser validado com banco e Redis ativos.
- Ainda não há paginação nos endpoints de listagem; pode ser tratado em fase posterior se necessário.
- Ainda não há filtros por data/categoria nos endpoints financeiros; não foi implementado para evitar expansão de escopo.
- O diagnóstico usa despesas com vencimento nos próximos 30 dias; isso deve ser confirmado como regra definitiva antes de dashboards ou inteligência avançada.

## Preparado para Fase 3

A Fase 2 deixa pronto:

- Base financeira persistente por usuário.
- Perfil financeiro central.
- Receita/despesa isoladas do restante da aplicação.
- Diagnóstico financeiro calculado sem dependência externa.
- Score financeiro 0-100.
- Budget engine automático.
- Contratos de API para futura integração com frontend.

A próxima fase recomendada é consolidar o domínio financeiro antes de qualquer avanço para market/catalog/intelligence. Se a Fase 3 for mercado ou catálogo de ativos, ela deve consumir o perfil/score financeiro sem alterar as regras já validadas aqui.
