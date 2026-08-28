# Fase 9 — Frontend Base + Identidade Visual

## Objetivo
Criar a base visual e estrutural definitiva do frontend do Vinance v2, sem alterar backend, regras financeiras, market, intelligence ou advisor.

## Decisões visuais
- Direção premium financeiro, moderna, limpa, sofisticada e confiável.
- Linguagem visual brasileira, com foco em sobriedade e leitura clara.
- Dark theme como prioridade, com suporte inicial a light theme.
- Evitado visual cyberpunk, neon exagerado, glow excessivo e template genérico de SaaS.

## Tipografia
- Headings: Sora.
- Texto/interface: Inter, com fallback para Manrope/system-ui.

## Paleta
- Fundo grafite escuro.
- Superfícies em camadas equilibradas.
- Verde financeiro sofisticado como cor principal.
- Dourado discreto como acento premium.
- Tons de alerta, sucesso e perigo definidos no design system.

## Estrutura criada
Nova estrutura em `frontend/src/`:
- `app/`
- `design-system/`
- `components/`
- `layouts/`
- `pages/`
- `features/`
- `services/`
- `hooks/`
- `routes/`
- `styles/`

O frontend legado da Fase 8 foi arquivado em:
- `frontend/_archived/src_legacy_phase8/`

## Design system criado
Arquivos:
- `frontend/src/design-system/colors.ts`
- `frontend/src/design-system/typography.ts`
- `frontend/src/design-system/spacing.ts`
- `frontend/src/design-system/shadows.ts`
- `frontend/src/design-system/radius.ts`
- `frontend/src/design-system/theme.ts`

## Componentes criados
- `Card`
- `Button`
- `Input`
- `Badge`
- `Tabs`
- `Modal`
- `EmptyState`
- `LoadingState`

## Rotas criadas
- `/login`
- `/dashboard`
- `/financial`
- `/market`
- `/intelligence`
- `/advisor`

## Layout base
Criado layout com:
- Sidebar compacta e elegante.
- Topbar com status visual e troca inicial de tema.
- Content container responsivo.
- Responsividade funcional para desktop, tablet e mobile.

## Dashboard base
Criado dashboard inicial usando mock local simples para validar layout:
- Financial score.
- Investment capacity.
- Allocation.
- Warnings.

## Advisor UI base
Criada estrutura visual inicial:
- Chat container.
- Message bubbles.
- Input.
- Typing state local.

Não há streaming, integração pesada ou lógica de advisor no frontend nesta fase.

## O que ficou mockado
- Dashboard base usa `frontend/src/features/dashboard/mock.ts`.
- Advisor UI usa mensagem local apenas para validar a experiência visual.

Esses mocks são locais, simples e não substituem regras do backend.

## Backend
Nenhum arquivo do backend foi alterado nesta fase.

## Preparação para Fase 10
A Fase 9 deixa preparado:
- Conectar login ao backend real.
- Consumir `/api/v1/intelligence/recommendations`.
- Consumir `/api/v1/advisor/chat`.
- Exibir dados financeiros reais.
- Evoluir páginas sem reconstruir layout ou design system.

## Validação executada
- `npm install`
- `npm run build`

- `npm install`: OK
- `npm run build`: OK
- `npm run dev`: OK, Vite iniciou em `http://localhost:3000/` durante validação controlada.

Observação: `npm install` reportou 1 vulnerabilidade moderada em dependência transitiva, sem bloquear build. Não foi executado `npm audit fix` para evitar alteração fora do escopo.
