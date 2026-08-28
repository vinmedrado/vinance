# Fase 11 — UX funcional com dados vazios + Onboarding Financeiro Inicial

## Objetivo

Melhorar a experiência real do usuário recém-criado, quando ainda não existem perfil financeiro, receitas, despesas, diagnóstico ou recomendações suficientes. Esta fase atua somente no frontend e mantém o backend aprovado intacto.

## Fluxos implementados

### Onboarding financeiro inicial

- Criado fluxo visual para usuário autenticado sem `FinancialProfile`.
- O dashboard deixa de quebrar quando o diagnóstico retorna erro por falta de perfil.
- O usuário recebe orientação clara sobre os dados necessários:
  - salário mensal;
  - reserva de emergência;
  - perfil de risco;
  - inadimplência.
- O formulário usa o endpoint real:
  - `POST /api/v1/financial/profile`.
- Após salvar, as queries financeiras são invalidadas/refetchadas para carregar diagnóstico e recomendações reais.

### Receitas vazias

- A página Financial agora mostra estado vazio quando não há receitas.
- Criado CTA para cadastrar a primeira receita.
- Formulário conectado ao endpoint real:
  - `POST /api/v1/financial/incomes`.
- Campos implementados:
  - `description`;
  - `amount`;
  - `income_type`;
  - `received_at`;
  - `is_recurring`.

### Despesas vazias

- A página Financial agora mostra estado vazio quando não há despesas.
- Criado CTA para cadastrar a primeira despesa.
- Formulário conectado ao endpoint real:
  - `POST /api/v1/financial/expenses`.
- Campos implementados:
  - `description`;
  - `amount`;
  - `category`;
  - `due_date`;
  - `paid_at` opcional;
  - `is_paid`;
  - `is_recurring`.

### Dashboard sem diagnóstico

- Dashboard passa a detectar ausência de perfil/diagnóstico sem renderizar cards falsos.
- Quando o contexto financeiro ainda não existe, exibe o onboarding real.
- Erros de API são exibidos com mensagem amigável e ação de nova tentativa.

### Intelligence sem dados suficientes

- A página Intelligence não inventa recomendações.
- Quando falta contexto financeiro, orienta o usuário a completar o perfil financeiro.
- Quando há allocation mas não há ativos rankeados, mantém a allocation real e mostra mensagem clara por classe.

### Advisor sem contexto completo

- O Advisor continua disponível caso o backend permita.
- Quando falta perfil financeiro, exibe aviso visual:
  - “Complete seu perfil financeiro para respostas mais personalizadas.”
- O chat continua sem streaming e sem renderização HTML perigosa.

## Componentes criados/alterados

Criados em `frontend/src/components/`:

- `ErrorState.tsx`
- `FormField.tsx`
- `MoneyInput.tsx`
- `SelectField.tsx`
- `ToggleField.tsx`
- `SubmitButton.tsx`
- `Toast.tsx`
- `OnboardingCard.tsx`

Alterados:

- `frontend/src/components/index.ts`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/FinancialPage.tsx`
- `frontend/src/pages/IntelligencePage.tsx`
- `frontend/src/pages/AdvisorPage.tsx`
- `frontend/src/styles/global.css`

## Endpoints usados

- `GET /api/v1/financial/profile`
- `POST /api/v1/financial/profile`
- `GET /api/v1/financial/diagnosis`
- `GET /api/v1/financial/incomes`
- `POST /api/v1/financial/incomes`
- `GET /api/v1/financial/expenses`
- `POST /api/v1/financial/expenses`
- `GET /api/v1/intelligence/recommendations`
- `POST /api/v1/advisor/chat`

## Loading, erro e feedback

- Estados de loading preservados com `LoadingState`.
- Estados vazios com CTA orientado.
- Erros de API exibidos por `ErrorState`.
- Feedback simples de sucesso com `Toast`.
- Botões de submit usam estado disabled/loading para reduzir double submit.

## O que continua simplificado

- Não há edição avançada de receitas/despesas.
- Não há exclusão de receitas/despesas.
- Não há wizard multi-step; o onboarding inicial é direto e funcional.
- Não há gráficos avançados.
- O Advisor segue sem streaming.

## Riscos remanescentes

- A UX depende dos contratos reais dos endpoints financeiros já aprovados.
- Alguns status de erro podem variar conforme validações do backend.
- Sem testes automatizados frontend dedicados nesta fase; a validação principal foi build TypeScript/Vite.

## Preparação para Fase 12

A Fase 11 deixa preparado:

- primeiro uso funcional para contas novas;
- base para wizard financeiro mais completo;
- componentes reutilizáveis de formulário;
- estados vazios padronizados;
- fluxo real para alimentar diagnóstico e intelligence sem mocks.

## Validação executada

- `npm install`: OK
- `npm run build`: OK
- Backend não alterado.
