# FASE 31 — Vinance Advanced Explanation Engine

## Objetivo

A Fase 31 melhora a camada de explicação do Budget Advisor para transformar a recomendação em uma análise quantitativa mais profissional, contextual e comparativa.

A implementação não altera syncs, schedules, fundamentals, scores, guardrails, trends, recommendation_score, banco de dados ou migrations. A mudança é exclusivamente derivada e aplicada na camada de explicação quando `explain=true`.

## Arquivos alterados

- `backend/app/intelligence/services/recommendation_explanation_service.py`
- `backend/app/intelligence/services/budget_advisor_service.py`

## Arquivos criados

- `backend/tests/test_fase31_advanced_explanation_engine.py`
- `FASE_31_ADVANCED_EXPLANATION_ENGINE.md`

## Melhorias implementadas

### 1. Explicação executiva

O retorno explicado agora inclui `executive_summary`, com resumo claro sobre:

- orçamento informado;
- ativo mais indicado;
- quantidade possível;
- uso do orçamento;
- confiança quantitativa;
- perfil utilizado.

### 2. Decision Card

Foi adicionado `decision_card`, contendo:

- `ticker`
- `action`
- `quantity`
- `price`
- `invested_amount`
- `remaining_budget`
- `budget_usage_pct`
- `recommendation_score`
- `confidence_score`
- `appreciation_signal`

### 3. Score Breakdown

Foi adicionado `score_breakdown`, separando os principais componentes quantitativos:

- `recommendation_score`
- `fundamental_score`
- `profile_score`
- `quality_score`
- `liquidity_score`
- `risk_score`
- `dividend_score`
- `momentum_score`

### 4. Ranking relativo

Foi adicionado `relative_position`, indicando:

- posição no ranking;
- total de candidatos;
- faixa relativa;
- texto explicativo.

Exemplo:

```json
{
  "rank": 1,
  "total_candidates": 20,
  "percentile_label": "TOP_5_PERCENT",
  "text": "Este ativo ficou em 1º lugar entre 20 opção(ões) compatíveis com seu orçamento e perfil."
}
```

### 5. Pontos fortes e pontos de atenção

A explicação agora retorna:

- `strengths`: motivos positivos específicos;
- `attention_points`: alertas quantitativos e limitações do sinal.

Exemplos de pontos fortes:

- score de perfil alto;
- qualidade elevada;
- liquidez forte;
- risco controlado;
- bom aproveitamento do orçamento.

Exemplos de atenção:

- tendência lateral;
- confiança baixa por histórico curto;
- momentum moderado;
- orçamento parcialmente ocioso.

### 6. Comparação com alternativas

Para `best_recommendation`, foi adicionado `comparison_with_alternatives`, comparando o ativo principal com até três alternativas seguintes do ranking.

A comparação explica de forma objetiva por que cada alternativa ficou abaixo, considerando:

- `recommendation_score`;
- `momentum_score`;
- combinação de perfil, risco, fundamentos e tendência.

### 7. Why Recommended mais específico

A lista `why_recommended` deixou de ser genérica e agora usa dados reais do item:

- guardrail e risco;
- `profile_score`;
- `score_total`;
- qualidade;
- liquidez;
- risco;
- dividendos;
- uso do orçamento;
- tendência e confiança.

### 8. Appreciation Text profissional

O texto de valorização estimada foi ajustado para quatro níveis:

- `HIGH`
- `MODERATE`
- `LOW`
- `UNKNOWN`

A linguagem evita promessa de retorno e usa termos como sinal quantitativo, tendência e confiança.

### 9. Explanation Quality

Foi adicionado `explanation_quality`:

- `STRONG`
- `GOOD`
- `BASIC`

A classificação considera:

- `confidence_label`;
- `trend_confidence`;
- `recommendation_score`.

## Segurança da recomendação

A explicação mantém disclaimer curto:

> Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno.

A implementação evita termos como:

- garantia de valorização;
- certeza de lucro;
- lucro certo.

## Comportamento preservado

### `explain=false` ou ausente

O contrato antigo do Budget Advisor permanece igual.

### `explain=true`

O Budget Advisor retorna:

```json
{
  "budget": "300.00",
  "market": "FII",
  "profile": "CONSERVATIVE",
  "best_recommendation": {},
  "alternatives": [],
  "disclaimer": "Esta é uma análise quantitativa baseada nos dados disponíveis, não uma garantia de retorno."
}
```

## Validação sugerida

```bash
docker compose build backend celery_worker celery_beat
docker compose up -d --force-recreate backend celery_worker celery_beat
```

Testes manuais:

```bash
curl.exe "http://localhost:8000/api/intelligence/budget-advisor?budget=300&market=FII&profile=CONSERVATIVE&limit=20&explain=true"

curl.exe "http://localhost:8000/api/intelligence/budget-advisor?budget=300&market=FII&profile=AGGRESSIVE&include_warnings=true&limit=20&explain=true"
```

## Resultado

A Fase 31 transforma o Budget Advisor explicado em uma análise mais clara, objetiva e profissional, mostrando não apenas qual ativo ficou em primeiro, mas também por que ele ficou acima das alternativas compatíveis com orçamento, perfil, risco e tendência.
