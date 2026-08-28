# Fase 6 — Intelligence Base

## Objetivo

Criar a primeira camada de inteligência do Vinance v2 sem advisor IA, sem Groq, sem ML treinado, sem backtest e sem chamadas externas.

## Arquivos criados

- `backend/app/intelligence/schemas.py`
- `backend/app/intelligence/allocation.py`
- `backend/app/intelligence/risk_rules.py`
- `backend/app/intelligence/asset_scoring.py`
- `backend/app/intelligence/service.py`
- `backend/app/intelligence/router.py`
- `backend/tests/test_intelligence_base.py`
- `FASE_6_INTELLIGENCE_BASE.md`

## Arquivos alterados

- `backend/app/api/v1/router.py`: registro do router autenticado de intelligence.

## Regras de allocation

Perfis base:

- Conservative: renda fixa 40%, FIIs 30%, ações 20%, ETFs 10%, cripto 0%.
- Moderate: renda fixa 25%, FIIs 25%, ações 25%, ETFs 15%, cripto 10%.
- Aggressive: renda fixa 10%, FIIs 20%, ações 30%, ETFs 20%, cripto 20%.

Ajustes obrigatórios implementados:

- Score financeiro abaixo de 40 bloqueia aggressive, zera cripto, reduz ações e aumenta renda fixa.
- Prioridade de reserva de emergência aumenta renda fixa e reduz ativos de risco.
- `high_risk_allowed=false` zera cripto e reduz ações.
- A soma final é normalizada para 100%.
- O retorno inclui percentual e valor em R$ por classe.

## Regras de risco

Implementado em `risk_rules.py`:

- `normalize_risk_profile`
- `can_recommend_high_risk`
- `apply_financial_constraints`
- `explain_risk_adjustments`

Regras:

- Score menor que 40 bloqueia risco alto.
- Inadimplência bloqueia cripto e reduz ações.
- Reserva menor que 3 meses prioriza renda fixa.
- Perfil inválido cai para `conservative`.

## Metodologia de scoring heurístico

O score é 0-100, sem ML e sem dados inventados. Campos ausentes recebem pontuação neutra de 50/100 e aparecem em `missing_fields`.

Classes:

- FIIs: `dy_12m`, `pvp`, `vacancia_fisica`, `liquidez_diaria`.
- Ações: `roe`, `pl`, `dy_12m`, `divida_liq_ebitda`, `volume_medio_diario`.
- ETFs: `taxa_adm`, `tracking_error`, `retorno_12m`, `volume_medio_diario`.
- BDRs: `dy_12m`, liquidez em BRL, proxy neutro de volatilidade e câmbio como risco.
- Cripto: `market_cap_rank`, `volume_24h_usd`, `price_change_30d_pct`, `ath_change_pct`.
- Renda fixa: `taxa_total_equiv`, `liquidez_dias`, `garantia_fgc`, `vencimento`.

## Endpoint

Criado endpoint autenticado:

- `GET /api/v1/intelligence/recommendations`

Query params opcionais:

- `amount`
- `risk_profile`

O endpoint retorna sugestão educacional, não ordem de compra.

## Limitações explícitas

- Não existe advisor IA.
- Não existe integração Groq.
- Não existe treinamento de ML.
- Não existe backtest.
- Não existe LSTM.
- Não existe Prophet.
- Não existe chamada externa.
- O ranking depende dos fundamentos já persistidos na base.

## Por que ML ainda não foi implementado

A Fase 6 prepara a base determinística e auditável antes de qualquer modelo treinado. Isso evita recomendações opacas, reduz risco de acoplamento prematuro e cria contrato estável para uma futura Fase 7.

## Testes criados

- Allocation conservative fecha 100%.
- Allocation moderate fecha 100%.
- Allocation aggressive fecha 100%.
- Score abaixo de 40 zera cripto.
- Reserva de emergência aumenta renda fixa.
- `high_risk_allowed=false` bloqueia cripto.
- Asset scoring não quebra com dados ausentes.
- Score sempre fica entre 0 e 100.
- Endpoint exige autenticação.
- Endpoint retorna allocation mesmo sem fundamentos.
- Intelligence não contém chamadas externas nem tokens de ML/advisor proibidos.

## Validação executada

Comandos previstos:

```bash
python -m compileall backend/app scripts workers  # OK
pytest  # não executou: ambiente do sandbox sem sqlalchemy instalado
alembic upgrade head  # não executado no sandbox por ausência de dependências/runtime de banco
```

## Riscos remanescentes

- Necessário popular fundamentos reais para ranking útil por classe.
- Pesos heurísticos podem ser calibrados em fase futura com dados históricos.
- Recomendações continuam educacionais e não substituem análise profissional.

## Preparação para Fase 7

A Fase 6 deixa prontos:

- Contrato de response para recomendações.
- Allocation engine desacoplado.
- Risk rules auditáveis.
- Scoring heurístico por classe.
- Serviço central para futura camada de advisor/IA, sem acoplar frontend.
