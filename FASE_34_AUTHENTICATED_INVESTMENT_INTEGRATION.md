# Fase 34 — Validação autenticada e integração real de `/investir`

## Objetivo e escopo

A Fase 34 endurece o fluxo da central de decisão entre rota protegida, sessão do usuário, API autenticada, normalização defensiva e componentes visuais.

O Recommendation Engine, suas fórmulas, Asset Scores, guardrails, trend signals, banco, migrations, `.env`, trading e modelos de ML não foram alterados. A única alteração backend é a exigência do usuário autenticado no endpoint de leitura `GET /api/intelligence/budget-advisor`.

Nenhum usuário foi criado no banco. Como não havia credencial de teste comprovada, os fluxos autenticados foram exercitados com fixtures no E2E e override de dependência no teste isolado do backend.

## Fluxo implementado

1. O acesso a `/investir` passa pelo `RequireAuth`.
2. A ausência ou expiração local do JWT redireciona para `/login`, preservando a rota de retorno.
3. Uma sessão presente só libera a rota após validação real em `GET /api/v1/me`.
4. O token identifica o cache da sessão; troca de token, logout e eventos entre abas não reutilizam o usuário anterior.
5. A consulta usa exclusivamente `GET /api/intelligence/budget-advisor?explain=true`, com Bearer, timeout e `AbortSignal` pelo cliente HTTP compartilhado.
6. A resposta desconhecida é normalizada e validada antes de alcançar os componentes.
7. A decisão visual é derivada uma única vez e compartilhada entre hero, rating, orçamento, tendência e resumo.
8. Respostas vazias, parciais ou inválidas recebem estados explícitos e fallbacks seguros.

## Autenticação e sessão

- usuário anônimo redirecionado para `/login`;
- retorno automático a `/investir` após login;
- `/me` obrigatório antes de renderizar conteúdo protegido;
- JWT expirado detectado antes da chamada a `/me`;
- expiração durante a sessão tratada por timer;
- 401 limpa somente a sessão que originou a requisição, sem invalidar um token mais novo;
- troca de token entre abas força uma nova chave de consulta;
- reload autenticado revalida `/me` sem depender do usuário persistido como dado confiável;
- logout cancela consultas, limpa sessão/cache e remove o conteúdo protegido;
- cancelamentos intencionais não são registrados como falhas de rede;
- payloads `200` inválidos de login, registro ou `/me` são rejeitados na fronteira.

## Integração e estados da interface

Foram validados os estados de:

- estado inicial;
- validação da sessão;
- loading da recomendação;
- erro HTTP;
- indisponibilidade de rede;
- timeout;
- resposta vazia;
- resposta parcial;
- resposta inválida;
- sucesso completo;
- reconsulta preservando e identificando o resultado anterior;
- ausência de alternativas;
- ausência de scores;
- ausência de explicações.

A normalização valida tipos, limites de scores, valores monetários, listas, recomendação principal, alternativas e blocos aninhados. Campos ausentes ou alternativas descartadas geram `integration_warnings`. Falhas de integração são registradas de forma estruturada, sem incluir token.

## Coerência visual

As seguintes invariantes foram consolidadas:

- `Evitar` domina rating, hero e ação quando há risco alto, bloqueio ou baixo potencial;
- `Aguardar` não recebe destaque de oportunidade forte;
- scores ausentes usam tom neutro e rating indisponível;
- score alto subordinado a um bloqueio continua visível como dado, acompanhado de explicação explícita;
- sinais locais positivos preservam sua semântica, mas não anulam a decisão global;
- texto técnico otimista da API não aparece como mensagem principal quando a ação é `Aguardar` ou `Evitar`;
- `Confidence Score` divergente de `Confidence Label` gera aviso e o valor numérico validado vira a fonte visual;
- ranking inferior não recebe badge positivo;
- alternativa bloqueada mantém ação negativa sem falsificar a cor de sua tendência local;
- hover não transforma cards negativos ou de atenção em verde.

## Arquivos de implementação

### Autenticação e rotas

- `frontend/src/services/api.ts`
- `frontend/src/features/auth/services/auth.service.ts`
- `frontend/src/features/auth/hooks/useAuth.ts`
- `frontend/src/features/auth/components/RequireAuth.tsx`
- `frontend/src/routes/AppRoutes.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/layouts/AppLayout.tsx`

### Central de decisão

- `frontend/src/pages/InvestmentWorkspacePage.tsx`
- `frontend/src/features/investment-workspace/services/investmentWorkspace.service.ts`
- `frontend/src/features/investment-workspace/types/investmentWorkspace.types.ts`
- `frontend/src/features/investment-workspace/utils/investmentDecision.ts`
- `frontend/src/features/investment-workspace/components/DecisionHeroCard.tsx`
- `frontend/src/features/investment-workspace/components/QuantChanceCard.tsx`
- `frontend/src/features/investment-workspace/components/BudgetUsageCard.tsx`
- `frontend/src/features/investment-workspace/components/RiskBadge.tsx`
- `frontend/src/features/investment-workspace/components/TrendInterpreterCard.tsx`
- `frontend/src/features/investment-workspace/components/StrengthChecklist.tsx`
- `frontend/src/features/investment-workspace/components/AlternativesComparison.tsx`
- `frontend/src/features/investment-workspace/components/ScoreBreakdownBars.tsx`
- `frontend/src/features/investment-workspace/components/ExecutiveSummaryCard.tsx`
- `frontend/src/features/investment-workspace/components/OpportunityRatingBadge.tsx`
- `frontend/src/styles/global.css`

### Contrato de leitura autenticado

- `backend/app/intelligence/router.py`
- `backend/tests/test_fase34_investment_workspace_auth.py`

### Infraestrutura de testes e build frontend

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vitest.config.ts`
- `frontend/tsconfig.tests.json`
- `frontend/playwright.config.ts`
- `frontend/tests/setup.ts`
- `frontend/tests/fixtures/investmentFixtures.ts`
- `frontend/tests/investmentDecision.test.mjs`
- `frontend/tests/unit/authFlow.test.tsx`
- `frontend/tests/unit/investmentWorkspacePage.test.tsx`
- `frontend/tests/e2e/investment-auth.spec.ts`
- `frontend/.gitignore`
- `frontend/.dockerignore`

## Testes e validações executadas

### Frontend

- `npm run test:frontend`: **29 aprovados**
  - 8 testes Node de tradução, decisão e normalização;
  - 21 testes Vitest/Testing Library de autenticação, estados e coerência visual.
- `npm run test:e2e`: **6 aprovados** em Chromium.
  - anônimo, login e retorno;
  - consulta autenticada, Bearer, método/parâmetros, reload e logout;
  - token inválido;
  - JWT já expirado;
  - expiração com `/investir` aberta;
  - desktop, 390 px e 320 px sem overflow horizontal.
- `npm run typecheck`: aprovado para aplicação e testes.
- `npm run lint`: aprovado. O script atual usa `tsc -b --noEmit`; não há ESLint configurado.
- `npm run build`: aprovado, 1.675 módulos transformados.

### Backend

- teste Fase 34 dentro de container temporário e dentro da imagem ativa: **3 aprovados**;
- acesso anônimo: 401;
- Bearer inválido: 401;
- usuário autenticado por override: caminho explicado 200, sem banco, com `limit`, `profile`, `include_warnings` e demais argumentos preservados.

Uma suíte histórica ampliada de inteligência obteve **27 de 28 testes aprovados**. A falha restante é `test_emergency_reserve_priority_aumenta_renda_fixa`, em uma regra de alocação financeira fora de `/investir`: os cenários `False` e `True` retornam 43%. Esse módulo não foi alterado porque corrigir a regra violaria o escopo e a proibição de modificar cálculos.

## Docker e navegador real

- imagens `backend` e `frontend` reconstruídas; somente esses dois containers foram recriados por necessidade;
- Celery, Postgres e Redis não foram reconstruídos;
- backend, Postgres e Redis saudáveis; frontend e serviços Celery em execução;
- `GET /health`: 200;
- `/login`: 200;
- `/investir`: 200 para o shell SPA;
- `/api/v1/me` anônimo: 401;
- `budget-advisor` anônimo ou com Bearer inválido: 401;
- navegador real: `/investir` anônimo terminou em `/login`, aviso correto visível e nenhum erro de console.

O primeiro build backend enviou 1,01 GB porque o projeto não possui `.dockerignore` na raiz. O cache Docker ficou sob pressão, foi limpo sem volumes (`19,2 GB` de cache descartável), e o Docker Desktop precisou ser reiniciado preservando os containers e dados. Um `.dockerignore` foi adicionado somente ao frontend, reduzindo seu contexto de cerca de 90 MB para 712 KB. O Docker backend não foi modificado.

## Limitações e riscos restantes

- Não houve login E2E contra uma conta real, pois nenhuma credencial de teste comprovada estava disponível; fixtures e overrides foram usados sem criar dados.
- O `npm install` reporta 16 vulnerabilidades transitivas existentes: 6 moderadas, 9 altas e 1 crítica. Não foi executado `npm audit fix` ou `--force` por risco de atualização quebrável fora do escopo.
- A captura manual de screenshot pelo driver do navegador excedeu o timeout uma vez; URL, DOM e console foram validados no navegador real, e a cobertura visual/responsiva foi concluída pelo Playwright.
- O repositório raiz continua sem `.dockerignore`, tornando rebuilds backend desnecessariamente pesados.
- Os testes E2E usam mocks de rede por ausência de credencial; o contrato HTTP autenticado real é coberto separadamente pelo teste FastAPI.

## Readiness

**Fase 34 pronta para aceite no escopo de `/investir`.** O fluxo protegido, a integração com `budget-advisor?explain=true`, os estados resilientes, a coerência visual, a responsividade, o build e os containers ativos foram validados. As limitações restantes são de credencial/infraestrutura/dependências e não bloqueiam a central de decisão implementada.

Nenhum commit, push ou merge foi realizado.
