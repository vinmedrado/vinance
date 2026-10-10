# Phase C legacy retirement

Esta decisão arquitetural registra a limpeza necessária para tornar o HEAD
autocontido. Ela não altera regras do Financial Autopilot 1–6 nem do Trading
V2.

## Retired

Os módulos abaixo não eram alcançados por `main.py`, routers, Celery, Beat ou
serviços canônicos. Eles importavam contratos já removidos ou implementavam
prioridade/alocação fixa concorrente com o Autopilot atual. Foram aposentados
fisicamente, em vez de receber shims:

- antigos serviços Intelligence de advanced backtest, asset scoring,
  contextual ML, financial capacity/goals, humanized recommendation,
  intelligent allocation, recommendation, personalized backtest, portfolio,
  risk e scenario simulation;
- antigos `advanced_advisor`, `decision_engine`, `investment_advisor` e
  `profile_dashboard` financeiros;
- o antigo `backend.app.decision.decision_engine`;
- o `PortfolioAllocator` e seu service de allocation, substituídos pela cadeia
  Financial Policy → Capital Allocation → Investment Orchestrator;
- o componente Streamlit `services/ui_components.py`, sem consumidor runtime e
  dependente de helpers inexistentes;
- os serviços Streamlit antigos de auth, i18n e currency, sem consumidor no
  runtime atual e dependentes de pacotes fora do ambiente suportado;
- testes que exigiam Enterprise, ERP, organization context e as stacks acima.

Referências a `services/ui_components.py` em `docs/patches/` são histórico de
patches Streamlit aposentados, não instruções do runtime atual.

## Fixed

- testes válidos que usavam o alias dependente de `pythonpath` `app.*` agora
  importam pelos caminhos canônicos `backend.app.*`;
- o `financial_analysis` preservado importa diretamente o calculador puro em
  `backend.app.domain.finance.calculator`;
- testes atuais que estavam fora de `pytest.ini` foram consolidados em
  `backend/tests`;
- a expectativa de `/ready` foi retirada da suíte atual. Readiness permanece
  requisito explícito de Production Hardening, não desta fase.

## Kept

- Financial State, Financial Policy, Capital Allocation, Investment
  Orchestrator, Action Plan e Continuous Autopilot;
- Recommendation Score, Budget Advisor, Investor Profile, Guardrails,
  monitoring e alerts canônicos;
- `financial_analysis` apenas como cálculo explícito sobre valores já
  owner-scoped;
- o calculador matemático puro de financiamento;
- models/pipelines Intelligence atuais;
- Trading V2 completo e `PAPER_ONLY`.

## Isolated optional analysis

Os engines de análise individual por classe em `backend/app/investment/engines`
permanecem importáveis e testados como utilitários isolados. Eles não estão
montados como uma segunda API, não alocam capital do Autopilot e não significam
suporte de produto para Renda Fixa ou Crypto Investment. Qualquer integração de
produto futura exigirá fase própria.

## Reproducible gate

`scripts/check_python_self_containment.py` analisa todos os Python rastreados,
valida sintaxe e resolve imports/símbolos internos. O gate também pode importar
os módulos runtime em subprocessos isolados:

```bash
python scripts/check_python_self_containment.py \
  --active-prefix backend.app \
  --active-prefix backend.trading \
  --active-prefix services \
  --active-prefix workers
```

O teste `backend/tests/test_repository_self_containment.py` preserva o gate
estático na suíte default.
