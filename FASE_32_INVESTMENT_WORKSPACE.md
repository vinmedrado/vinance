# FASE 32 — Vinance Investment Workspace

## Objetivo

Transformar o frontend do Vinance em uma interface principal de apoio à decisão do investidor, consumindo exclusivamente as APIs existentes do backend e apresentando as informações produzidas pelo Recommendation Engine.

## Escopo respeitado

Esta fase foi aplicada exclusivamente no frontend e na orquestração local do serviço frontend no `docker-compose.yml`.

Não foram alterados:

- Backend
- Syncs
- Celery
- Schedules existentes
- Banco de dados
- Migrations
- Asset Scores
- Guardrails
- Trend Signals
- Recommendation Score Engine
- Machine Learning
- Backtests

## Página criada

Foi criada a nova página:

```text
/frontend/src/pages/InvestmentWorkspacePage.tsx
```

Rota adicionada:

```text
/investir
```

Item de menu adicionado:

```text
Investir
```

## Integração com API

A página consome exclusivamente:

```http
GET /api/intelligence/budget-advisor
```

Sempre utilizando:

```text
explain=true
```

Serviço criado:

```text
frontend/src/features/investment-workspace/services/investmentWorkspace.service.ts
```

Tipos criados:

```text
frontend/src/features/investment-workspace/types/investmentWorkspace.types.ts
```

Nenhum score, ranking, guardrail, tendência ou recommendation score é recalculado no frontend. O frontend apenas renderiza os campos retornados pelo backend.

## Filtros implementados

Painel superior com:

- Orçamento
- Mercado
- Perfil
- Checkbox para incluir ativos classificados como `WARNING`
- Botão `Gerar recomendação`

Perfis disponíveis:

- Conservador → `CONSERVATIVE`
- Moderado → `MODERATE`
- Agressivo → `AGGRESSIVE`

Mercados disponíveis no dropdown:

- Todos
- FIIs
- Ações
- ETFs
- BDRs
- Cripto

Observação: a API atual do Budget Advisor trabalha com um mercado por chamada. A opção `Todos` foi mantida na UI como opção visual solicitada, sem implementar regra de recomendação no frontend.

## Componentes visuais criados na página

A tela renderiza:

- Card principal da recomendação
- Executive Summary
- Decision Card
- Score Breakdown com barras CSS
- Por que recomendamos
- Pontos fortes
- Pontos de atenção
- Riscos
- Posição relativa
- Comparação com alternativas
- Chance de valorização
- Disclaimer retornado pela API
- Outras recomendações

## Campos exibidos no card principal

- Ticker
- Mercado
- Quantidade sugerida
- Preço
- Valor investido
- Saldo restante
- Recommendation Score
- Confidence Score
- Confidence Label
- Profile Score
- Score Fundamentalista
- Momentum Score
- Trend Label
- Trend Confidence
- Risk Level
- Status

## Design

Foram adicionados estilos dedicados ao `global.css`:

- Dark mode preservado
- Cards arredondados
- Layout responsivo
- Barras horizontais via CSS
- Badges de risco em verde/amarelo/vermelho
- Cards menores para alternativas
- Espaçamento amplo para leitura executiva

Nenhuma biblioteca pesada de gráfico foi adicionada.

## Dockerização do frontend

Foi adicionado o serviço `frontend` ao `docker-compose.yml`:

```yaml
frontend:
  build:
    context: ./frontend
    args:
      VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8000}
  ports:
    - "3000:80"
  depends_on:
    backend:
      condition: service_healthy
  restart: unless-stopped
```

Também foi ajustado o `frontend/Dockerfile` para aceitar:

```text
VITE_API_BASE_URL
```

Assim, ao executar:

```bash
docker compose up -d
```

o ambiente passa a subir também o frontend.

## Validações realizadas

Validação executada com sucesso:

```bash
cd frontend
npm install
npm run build
```

Resultado:

```text
✓ built
```

Também foram preservados os contratos antigos:

- `explain=false` não foi alterado no backend.
- Nenhuma API existente foi modificada.
- Nenhuma regra de recomendação foi duplicada no frontend.

## Observação de ambiente

A validação de `docker compose config` não pôde ser executada neste ambiente porque o binário `docker` não está disponível no runtime local da análise.

## Resultado

A partir desta fase, o usuário consegue acessar a tela `Investir`, informar orçamento e perfil, gerar uma recomendação inteligente com `explain=true`, visualizar o ativo principal, entender os motivos, riscos, pontos fortes, posição relativa e alternativas, mantendo toda a inteligência centralizada no backend.
