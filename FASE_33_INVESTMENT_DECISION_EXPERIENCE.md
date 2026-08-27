# FASE 33 — Vinance Investment Decision Experience

## Objetivo

Transformar a rota de investimento do Vinance em uma central de decisão profissional. A interface passa a responder, em ordem de importância, qual ativo está mais bem posicionado, qual ação visual é sugerida, quantas cotas cabem no orçamento, quanto será investido, quanto sobra e quais sinais sustentam ou limitam a oportunidade.

## Escopo respeitado

A implementação desta fase é exclusivamente frontend.

Não foram alterados:

- backend ou APIs;
- banco de dados ou migrations;
- Recommendation Engine;
- Asset Scores;
- guardrails;
- Trend Signals;
- scheduler ou Celery;
- Docker do backend.

## Tela alterada

A experiência foi aplicada à rota autenticada:

```text
/investir
```

Arquivo de composição da página:

```text
frontend/src/pages/InvestmentWorkspacePage.tsx
```

A página foi reorganizada em três blocos de leitura:

1. Decisão: oportunidade principal, ação, orçamento, risco, chance, tendência e potencial.
2. Explicação: resumo, ranking, scores, motivos, pontos fortes e pontos de atenção.
3. Alternativas: comparação direta e as próximas dez posições do ranking.

## Componentes criados

Os componentes foram extraídos para:

```text
frontend/src/features/investment-workspace/components/
```

### `DecisionHeroCard`

Card principal com:

- melhor oportunidade do dia;
- ticker e mercado;
- risco traduzido;
- quantidade sugerida;
- preço atual;
- valor investido;
- saldo restante;
- ação visual sugerida;
- rating de oportunidade.

### `QuantChanceCard`

Traduz o `recommendation_score` para uma leitura simples e apresenta:

- Chance quantitativa;
- Confidence Score;
- Confidence Label traduzido;
- Explanation Quality traduzida.

Faixas utilizadas:

| Recommendation Score | Leitura |
|---:|---|
| 95 ou mais | Excelente |
| 90 a 94,99 | Muito alta |
| 80 a 89,99 | Alta |
| 70 a 79,99 | Boa |
| 60 a 69,99 | Moderada |
| abaixo de 60 | Baixa |

### `BudgetUsageCard`

Apresenta valor sugerido, orçamento total, percentual utilizado, quantidade, saldo livre e preço unitário. A barra de uso é implementada somente com CSS.

### `RiskBadge`

Traduz e colore o risco de forma contextual:

- `LOW` → Baixo, verde;
- `MEDIUM` → Médio, amarelo;
- `HIGH` → Alto, vermelho;
- `UNKNOWN` ou valor não reconhecido → Indefinido, cinza.

### `TrendInterpreterCard`

Traduz o sinal técnico e mostra a explicação correspondente:

- `UPTREND` → Tendência de alta;
- `SIDEWAYS` → Mercado lateral;
- `DOWNTREND` → Tendência de baixa;
- `INSUFFICIENT_HISTORY` → Histórico insuficiente.

O componente também apresenta `momentum_score`, `trend_confidence`, `appreciation_signal` traduzido e `appreciation_text`.

### `StrengthChecklist`

Usado em dois contextos:

- checklist de `why_recommended`;
- cartão positivo de `strengths`.

### `AttentionPointsCard`

Exibe `attention_points` em um cartão amarelo com leitura de cautela.

### `AlternativesComparison`

Exibe:

- `comparison_with_alternatives`, com ticker e motivo;
- no máximo dez itens de `alternatives`;
- ranking;
- ticker e mercado;
- recommendation score;
- confidence score;
- risco e tendência traduzidos;
- quantidade possível;
- valor investido.

### `ScoreBreakdownBars`

Renderiza oito barras horizontais em CSS:

- Recommendation Score;
- Fundamental Score;
- Profile Score;
- Quality Score;
- Liquidity Score;
- Risk Score;
- Dividend Score;
- Momentum Score.

### `ExecutiveSummaryCard`

Destaca `executive_summary` e apresenta explicitamente os quatro elementos de `relative_position`:

- `rank`;
- `total_candidates`;
- `percentile_label` traduzido;
- `text`.

### `OpportunityRatingBadge`

Converte a média visual entre `recommendation_score` e `confidence_score` em cinco faixas. A média só é calculada quando os dois scores estão presentes; dados incompletos recebem leitura conservadora:

| Média visual | Rating |
|---:|---|
| 90 ou mais | ★★★★★ Excelente oportunidade |
| 80 a 89,99 | ★★★★☆ Boa oportunidade |
| 70 a 79,99 | ★★★☆☆ Oportunidade moderada |
| 60 a 69,99 | ★★☆☆☆ Aguardar |
| abaixo de 60 | ★☆☆☆☆ Evitar |

Esse rating é somente uma tradução visual. Ele não substitui nem modifica os scores do backend. Para evitar mensagens contraditórias no mesmo hero, a ação visual tem precedência de apresentação: `Evitar` limita o rating a uma estrela e `Aguardar` a duas estrelas. A regra `Comprar` preserva a faixa calculada pelos dois scores.

## Ação visual sugerida

A função de apresentação está centralizada em:

```text
frontend/src/features/investment-workspace/utils/investmentDecision.ts
```

Precedência adotada para resolver condições simultâneas:

1. **Evitar** quando qualquer condição de bloqueio estiver presente: `risk_level = HIGH`, `status = BLOCKED` ou `appreciation_signal = LOW`.
2. **Aguardar** quando `trend_label = SIDEWAYS` e `momentum_score < 45`.
3. **Comprar** quando todas as condições forem atendidas: `status = APPROVED`, `risk_level = LOW`, `recommendation_score >= 75` e `confidence_score >= 80`.
4. **Aguardar** como fallback quando nenhuma regra anterior produzir decisão.

Essa precedência é conservadora e existe apenas na camada visual. Nenhum score, status ou sinal é recalculado.

## Integração com a API

A tela consome exclusivamente:

```http
GET /api/intelligence/budget-advisor?explain=true
```

Parâmetros enviados:

- `budget`;
- `market`;
- `profile`;
- `limit=20`;
- `include_warnings`;
- `explain=true`.

O seletor de mercado foi limitado aos mercados realmente aceitos por esse endpoint:

- FII;
- Ações;
- ETF;
- BDR.

Também foi adicionada uma normalização defensiva da resposta na fronteira do frontend. Ela valida o objeto principal, a recomendação e a lista de alternativas sem derivar dados de investimento.

## Campos consumidos

### Resposta principal

- `budget`
- `market`
- `profile`
- `best_recommendation`
- `alternatives`
- `disclaimer`

### Recomendação

- `ticker`
- `market`
- `recommendation_title`
- `price`
- `quantity_possible`
- `invested_amount`
- `remaining_budget`
- `budget_usage_pct`
- `status`
- `risk_level`
- `recommendation_score`
- `score_total`
- `profile_score`
- `score_quality`
- `score_liquidity`
- `score_risk`
- `score_dividend`
- `confidence_score`
- `confidence_label`
- `explanation_quality`
- `trend_label`
- `momentum_score`
- `trend_confidence`
- `appreciation_signal`
- `appreciation_text`
- `executive_summary`
- `decision_summary`
- `decision_card`
- `score_breakdown`
- `relative_position`
- `why_recommended`
- `strengths`
- `attention_points`
- `comparison_with_alternatives`
- `disclaimer`

## Decisões visuais e de UX

- Dark mode preservado como experiência principal, com suporte ao tema claro existente.
- Hierarquia visual separada entre decisão, explicação e alternativas.
- Verde reservado a sinais positivos, amarelo a cautela, vermelho a bloqueio/risco e cinza a informação indefinida.
- Badges contextuais evitam interpretar `HIGH` da mesma forma para risco, confiança e potencial.
- Valores numéricos ausentes são apresentados como `—`, evitando que ausência seja confundida com zero financeiro.
- Barras e medidores usam CSS e atributos acessíveis `meter`/`progressbar`.
- Medidores omitem `aria-valuenow` quando a API não informa o valor e limitam valores válidos à escala visual de 0 a 100.
- A página possui um `h1`, estados assíncronos com `status`/`alert` e contraste reforçado para textos auxiliares nos temas escuro e claro.
- Listas possuem ícones semânticos e chaves estáveis mesmo quando o backend repete textos.
- Layout responsivo sem rolagem horizontal nos breakpoints validados.
- Uma nova submissão com os mesmos filtros refaz explicitamente a consulta, permitindo atualizar os dados sem alterar o formulário.

## Validações realizadas

### TypeScript e build de produção

Executado com sucesso:

```text
npm run build
```

Resultado:

```text
✓ 1673 modules transformed
✓ built
```

### Testes automatizados do frontend

Executado com sucesso:

```text
npm run test:investment-decision
```

Foram aprovados sete testes cobrindo:

- fronteiras da chance quantitativa;
- precedência entre `Evitar`, `Aguardar` e `Comprar`;
- cinco faixas do rating e alinhamento com a ação;
- traduções e fallbacks;
- normalização defensiva de listas e recomendações parciais;
- rejeição de resposta raiz inválida;
- endpoint único e presença obrigatória de `explain=true`.

### Build no Docker

Executado com sucesso usando o Dockerfile existente do frontend e Node 20:

```text
docker compose build frontend
docker compose up -d --no-deps frontend
```

O serviço `frontend` iniciou na porta `3000`, o backend permaneceu saudável na porta `8000` e `http://localhost:3000/investir` respondeu `HTTP 200` pelo Nginx.

### Contrato real da API

Foi executada uma chamada real com:

```text
budget=300
market=FII
profile=CONSERVATIVE
limit=20
include_warnings=false
explain=true
```

Na validação, a API retornou:

- recomendação principal `GARE11`;
- 36 cotas;
- investimento de R$ 296,28;
- saldo de R$ 3,72;
- Recommendation Score 87,3;
- Confidence Score 100;
- risco `LOW`;
- tendência `UPTREND`;
- potencial `HIGH`;
- oito scores no breakdown;
- nove motivos;
- seis pontos fortes;
- um ponto de atenção;
- três comparações;
- dezenove alternativas, limitadas visualmente às dez primeiras.

### Renderização dos componentes com dados reais

Os componentes foram renderizados com a resposta real da API. Foram confirmados:

- ticker, quantidade, preço, investimento e saldo;
- ação `Comprar`;
- chance `Alta`;
- confiança `Alta`;
- qualidade `Robusta`;
- risco `Baixo`;
- tendência `Tendência de alta`;
- potencial `Alto`;
- rating `★★★★★ Excelente oportunidade`;
- oito barras de score;
- motivos, pontos fortes e pontos de atenção;
- resumo executivo e ranking Top 5%;
- comparação e exatamente dez alternativas.

### Responsividade

Validação no navegador com os componentes reais e dados vivos:

- 1440 × 1000: três cards no resumo, quatro métricas no hero e duas colunas de alternativas;
- 390 × 844: uma coluna em todas essas áreas;
- nenhuma rolagem horizontal nos dois tamanhos.

### Limite da validação autenticada

A validação da rota autenticada foi parcial: o Nginx e a SPA responderam em `/investir`, e uma sessão anônima foi corretamente redirecionada para `/login`, conforme o comportamento já existente. Para não criar usuário nem alterar o banco, não foi executado um fluxo autenticado ponta a ponta. A inspeção visual foi feita em uma prévia local isolada dos mesmos componentes e estilos, alimentada pela resposta real da API.

## Resultado

A tela de investimento passa a priorizar decisão e entendimento. O usuário consegue identificar imediatamente o ativo principal, a quantidade, o investimento, o saldo, a ação visual, o risco, a confiança, o potencial e as alternativas, mantendo toda a inteligência quantitativa no backend.
