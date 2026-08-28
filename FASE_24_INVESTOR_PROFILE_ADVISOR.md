# FASE 24 — Vinance Investor Profile Advisor

## Objetivo
Adicionar perfis de investidor ao Budget Advisor para que as recomendações sejam ajustadas conforme o perfil conservador, moderado ou agressivo.

## Escopo implementado

- Criado o módulo `backend/app/intelligence/services/investor_profile_service.py`.
- Criadas constantes/valores de perfil:
  - `CONSERVATIVE`
  - `MODERATE`
  - `AGGRESSIVE`
- Criadas funções:
  - `normalize_profile(profile)`
  - `apply_profile_filters(items, profile, include_warnings=False)`
  - `get_diversified_allocation(profile)`
  - `calculate_profile_score(item, profile)`
- O endpoint existente `/api/intelligence/budget-advisor` agora aceita `profile` sem quebrar compatibilidade.
- O endpoint `/api/intelligence/budget-advisor/diversified` também aceita `profile`.
- Quando `profile` não é informado, o padrão é `MODERATE`.

## Regras por perfil

### CONSERVATIVE
- Retorna apenas `APPROVED`.
- Exige `risk_level = LOW`.
- Exclui ativos com `score_risk` baixo.
- Ordena priorizando qualidade, liquidez e risco.
- Alocação diversificada:
  - 50% ETF
  - 30% FIIs
  - 20% Ações
  - 0% BDR

### MODERATE
- Perfil padrão.
- Retorna `APPROVED`.
- Permite `WARNING` somente com `include_warnings=true`.
- Aceita `risk_level` LOW e MEDIUM.
- Ordena por `score_total`.
- Alocação diversificada:
  - 40% FIIs
  - 30% Ações
  - 20% ETFs
  - 10% BDRs

### AGGRESSIVE
- Nunca retorna `BLOCKED`.
- Permite `WARNING` quando `include_warnings=true`.
- Ordena priorizando `score_total`, `score_value` e `score_dividend`.
- Alocação diversificada:
  - 30% Ações
  - 25% FIIs
  - 25% ETFs
  - 20% BDRs

## Endpoints atualizados

```http
GET /api/intelligence/budget-advisor?budget=150&market=FII&limit=20&profile=CONSERVATIVE
GET /api/intelligence/budget-advisor?budget=150&market=FII&limit=20&profile=MODERATE
GET /api/intelligence/budget-advisor?budget=150&market=FII&limit=20&profile=AGGRESSIVE&include_warnings=true
GET /api/intelligence/budget-advisor/diversified?budget=500&profile=CONSERVATIVE
GET /api/intelligence/budget-advisor/diversified?budget=500&profile=AGGRESSIVE
```

## Campos adicionados ao retorno

- `profile`
- `profile_score`
- `status`
- `risk_level`
- `reasons_json`

## Testes

Arquivo criado:

- `backend/tests/test_fase24_investor_profile_advisor.py`

Coberturas:

- Sem profile usa `MODERATE`.
- Profile inválido gera erro.
- Conservador não retorna `WARNING`.
- Agressivo não retorna `BLOCKED`.
- Carteira diversificada muda alocação por profile.
- Comportamento antigo continua funcionando com profile padrão.

## Arquivos alterados/criados

Criados:

- `backend/app/intelligence/services/investor_profile_service.py`
- `backend/tests/test_fase24_investor_profile_advisor.py`
- `FASE_24_INVESTOR_PROFILE_ADVISOR.md`

Alterados:

- `backend/app/intelligence/services/budget_advisor_service.py`
- `backend/app/intelligence/router.py`
- `backend/app/intelligence/schemas.py`

## Restrições respeitadas

- Não alterado syncs.
- Não alterado CoinGecko.
- Não alterado Investidor10.
- Não alterado fundamentals.
- Não alterado `asset_scores`.
- Não alterado `asset_recommendation_guardrails`.
- Não alterado frontend.
- Budget Advisor mantido e ampliado de forma retrocompatível.
