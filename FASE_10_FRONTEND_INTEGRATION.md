# Fase 10 — Frontend Integration

## Objetivo
Conectar o frontend aprovado na Fase 9 ao backend FastAPI real aprovado até a Fase 8, sem alterar backend, regras financeiras, market, intelligence ou advisor.

## Endpoints integrados

### Autenticação
- `POST /api/v1/register`
- `POST /api/v1/login`
- `GET /api/v1/me`

Implementado login real, registro simples, persistência de JWT em `localStorage`, logout com limpeza de sessão e proteção de rotas privadas.

### Financial
- `GET /api/v1/financial/diagnosis`
- `GET /api/v1/financial/profile`
- `POST /api/v1/financial/profile`
- `GET /api/v1/financial/incomes`
- `POST /api/v1/financial/incomes`
- `GET /api/v1/financial/expenses`
- `POST /api/v1/financial/expenses`

A página financeira possui listagem e criação simples de receitas/despesas e upsert de perfil financeiro. Não foi criada edição complexa.

### Intelligence
- `GET /api/v1/intelligence/recommendations`

Dashboard e página Intelligence consomem alocação, score, warnings, metodologia e ativos rankeados retornados pelo backend.

### Advisor
- `POST /api/v1/advisor/chat`

Advisor conectado ao endpoint real, com histórico local apenas da sessão atual, loading state e fallback de erro. Não há streaming nem renderização HTML perigosa.

### Market
- `GET /api/v1/market/macro`
- `GET /api/v1/market/renda-fixa`
- `GET /api/v1/market/fundamentals/fii`
- `GET /api/v1/market/fundamentals/acoes`
- `GET /api/v1/market/fundamentals/etf`
- `GET /api/v1/market/fundamentals/bdr`
- `GET /api/v1/market/fundamentals/cripto`

A tela Market mostra listas simples de indicadores e fundamentos, sem screener avançado.

## API layer
Criado wrapper com `axios` em `frontend/src/services/api.ts`:
- `baseURL` por env;
- prefixo `/api/v1` configurável;
- timeout de 15s;
- interceptor de autenticação;
- normalização de erros;
- limpeza de sessão em `401`;
- sem log de token.

Criado `frontend/.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_PREFIX=/api/v1
```

## React Query
Criado provider global:
- `frontend/src/app/providers/QueryProvider.tsx`

Hooks por domínio:
- `features/auth/hooks/useAuth.ts`
- `features/financial/hooks/useFinancial.ts`
- `features/intelligence/hooks/useIntelligence.ts`
- `features/advisor/hooks/useAdvisorChat.ts`
- `features/market/hooks/useMarket.ts`

## Estrutura de features
Cada domínio recebeu estrutura com `hooks`, `services`, `types` e `components` preparado para evolução:
- `frontend/src/features/auth/`
- `frontend/src/features/financial/`
- `frontend/src/features/market/`
- `frontend/src/features/intelligence/`
- `frontend/src/features/advisor/`

## Estados de loading/error/empty
Implementados estados de carregamento, erro e vazio nas páginas principais usando os componentes visuais da Fase 9.

## Páginas conectadas
- `/login`: auth real;
- `/dashboard`: diagnosis + recommendations;
- `/financial`: profile, incomes, expenses;
- `/market`: macro + fundamentos;
- `/intelligence`: recommendations;
- `/advisor`: advisor chat real.

## O que ainda está simplificado
- Sem refresh token real;
- Sem edição/exclusão de receitas e despesas;
- Sem charts avançados;
- Sem streaming no advisor;
- Sem markdown complexo no advisor;
- Sem screener avançado de mercado.

## Segurança frontend
- Rotas privadas protegidas;
- Token não é enviado para console/log;
- Logout limpa sessão;
- `401` limpa sessão no interceptor;
- Advisor renderiza texto puro via React, sem `dangerouslySetInnerHTML`.

## Validação executada
- `npm install`: OK;
- `npm run build`: OK;
- `npm run dev`: OK, Vite iniciou na porta 3000.

## Riscos remanescentes
- Necessário backend ativo com Postgres/Redis para validação funcional ponta a ponta;
- Caso o backend esteja sem dados financeiros, páginas exibem mensagens de erro/vazio conforme resposta real;
- Auth usa JWT local sem refresh token, conforme escopo atual.

## Preparado para Fase 11
- Refinamento de UX com dados reais;
- Formulários mais completos;
- Tratamento de sessão expirada com redirect dedicado;
- Dashboards visuais com gráficos reais;
- Advisor com melhor experiência conversacional sem alterar o contrato backend.
