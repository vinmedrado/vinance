# Action Plan V1

## Objetivo e fronteiras

`action-plan-v1` transforma a cadeia canônica já decidida pelo VinanceOS em um
plano único, ordenado e explicável:

```text
household-financial-state-v1
  -> financial-policy-v1
  -> capital-allocation-v1
  -> investment-orchestrator-v1
  -> action-plan-v1
```

O Action Plan não recalcula situação financeira, prioridade, capital disponível,
perfil, score, guardrail, mercado ou quantidade. Ele somente converte os
contratos congelados anteriores em ações compreensíveis e preserva a referência
exata que originou cada item.

A v1 é exclusivamente uma decisão/orientação. Não possui estado de execução,
não confirma aportes ou pagamentos e não integra corretora, banco, Open Finance,
PIX ou Trading.

## Cadeia de entrada

Antes de produzir ações, o engine verifica household, moeda, período, IDs,
versões de engine, versões de ruleset, fingerprints e vínculos State -> Policy
-> Allocation -> Orchestration. Também reconcilia o investment budget, o
capital sugerido e o caixa remanescente. Uma mistura entre households, decisões
divergentes ou cadeia parcialmente live/parcialmente persistida nunca é aceita
como plano válido. Uma nova versão upstream fica bloqueada até ser declarada
compatível por uma nova versão do contrato A5.

O engine e o ruleset são versionados como `action-plan-v1` e
`action-plan-rules-v1`. Para a mesma cadeia congelada e o mesmo ruleset, o
payload e seu fingerprint são determinísticos.

Existem dois modos explícitos. `GET /action-plan` pode produzir uma avaliação
live efêmera, em que todos os IDs de decisão são nulos. As rotas baseadas em uma
Orchestration persistida usam uma cadeia inteiramente congelada. Em resposta
live `BLOCKED`, moeda, período, budgets ou fingerprints ausentes permanecem
`null`; não são preenchidos com zero, BRL ou hashes substitutos. Somente uma
cadeia monetária completa e inteiramente congelada pode ser persistida em
`action_plan_decisions`.

## Status e tipos de ação

Status formais:

- `BLOCKED`: a cadeia é inválida ou Policy, Allocation ou Orchestration possui
  um gate crítico `BLOCKED`/`DATA_BLOCKED`; ações explicativas ainda podem
  existir, mas o plano não é classificado como pronto;
- `PARTIAL`: a cadeia não possui gate crítico, porém depende de informação não
  crítica ou apresenta somente parte das orientações;
- `READY`: as ações do ciclo foram consolidadas sem bloqueio material;
- `NO_ACTION_REQUIRED`: a cadeia válida não exige uma ação nova no ciclo.

Tipos estruturados:

- informação: `COMPLETE_INFORMATION`;
- financeiro: `STABILIZE_CASHFLOW`, `DEBT_PAYMENT`,
  `EMERGENCY_RESERVE_CONTRIBUTION` e `GOAL_CONTRIBUTION`;
- investimento: `INVESTMENT_BUY`, `INVESTMENT_WAIT` e `INVESTMENT_AVOID`;
- preservação: `HOLD_CASH`;
- ausência deliberada de ação: `NO_ACTION`.

Itens sem valor conhecido mantêm `amount = null`; ausência nunca vira zero. BUY,
WAIT e AVOID preservam a semântica do Orchestrator e guardrails sempre
prevalecem. WAIT, AVOID e BLOCKED nunca são promovidos a compra.

## Ordem, ownership e conservação

A ordem financeira vem da priority stack da Policy e dos ranks da Allocation.
O plano não promove investimento acima de dívida, reserva ou goal priorizados.
Cada ação financeira preserva `PERSONAL` ou `HOUSEHOLD`, usuário proprietário e
alvo original quando disponíveis; `PERSONAL` exige `owner_user_id`. Ownership
ausente continua ausente — em particular, o bucket consolidado de investimento
não é convertido implicitamente em `HOUSEHOLD`. Não existe divisão 50/50 ou
transferência implícita entre membros.

Os valores monetários são `Decimal` e reutilizam os centavos já decididos pelos
engines anteriores. As invariantes são:

```text
sum(financial action amounts) <= authorized non-investment allocation
sum(INVESTMENT_BUY amounts) <= orchestration.suggested_capital
sum(INVESTMENT_BUY amounts) + HOLD_CASH <= orchestration.investment_budget
speculative_capital = 0
trading_dispatch = false
```

WAIT e AVOID não comprometem capital. O caixa que o Orchestrator manteve sem
alocação aparece explicitamente como `HOLD_CASH` e nunca desaparece do plano.

## Investimentos e freshness

O plano reutiliza somente as oportunidades congeladas pelo Investment
Orchestrator. Quando disponíveis, preserva ticker, classe, quantidade candidata,
capital comprometido, preço de referência, timestamp, fonte, freshness, score e
guardrail. Preço de referência é apresentado como o valor usado na decisão, não
como cotação atual ou garantia de execução.

`NO_SUITABLE_OPPORTUNITY` produz orientação de aguardar e manter capital, não uma
compra artificial. A central `/investir` continua sendo a experiência
especializada; o Action Plan apenas fornece contexto e links seguros como “Ver
oportunidade”, sem CTA transacional.

## Explicabilidade

Cada ação registra motivo, evidências, warnings, blockers, informação ausente e
referência ao engine/decisão de origem. O payload também contém rule traces e
fingerprints de cada etapa. Assim é possível explicar o que fazer, quanto, em
qual ordem, por que a ação existe, o que ficou bloqueado e que dado poderia
alterar o plano.

O engine não gera previsão de retorno, promessa de alta, conselho de quitação ou
qualquer texto financeiro sem uma decisão estruturada anterior.

## Persistência, histórico e idempotência

`action_plan_decisions` guarda a decisão imutável e a cadeia completa de IDs,
versões e fingerprints. O payload congelado é usado diretamente em detalhe e
histórico; nunca é recalculado com mercado ou regras atuais.

Uma FK composta impede associação com outra decisão A4, household ou cadeia e
ancora budget, suggested capital e remaining cash. Constraints do banco
garantem valores não negativos e conservação de investimento. A conservação
financeira também é validada pelo engine contra as allocations A3 e protegida
pelo fingerprint/payload imutável; ela não é recalculada pelo A5. Triggers
PostgreSQL rejeitam `UPDATE`, `DELETE` e `TRUNCATE`. `Idempotency-Key` é única
por household, e também há unicidade pela decisão de Orchestration e versões do
engine/ruleset.

A listagem histórica inclui data, status, ação principal, preview das primeiras
ações, quantidade de ações, capital autorizado de investimento, totais
financeiros, compras sugeridas e caixa preservado. O detalhe continua usando
exclusivamente o payload congelado.

## API e segurança

Endpoints autenticados sob `/api/v1/financial/households/{household_id}`:

- `GET /action-plan`;
- `GET /action-plan/from-orchestration/{orchestration_id}`;
- `POST /action-plan/decisions`;
- `GET /action-plan/history`;
- `GET /action-plan/history/{action_plan_id}`.

Todos exigem membership ativo, isolam households, evitam enumeração cruzada e
retornam `Cache-Control: private, no-store`. A autorização canônica concede aos
membros ativos a visão consolidada do household, incluindo os itens pessoais
que compõem aquela decisão; não existe acesso por usuário externo ao household.
Não existe endpoint de edição ou exclusão.

## Frontend

“Seu plano de ação” fecha o fluxo visual iniciado em “Minha situação
financeira”. A tela prioriza ação, valor, ordem, motivo e status, com grupos para
informação, finanças, investimentos e espera/caixa. Estados BLOCKED, PARTIAL e
NO ACTION são experiências de negócio, não erros técnicos. O histórico abre
somente payload congelado e identifica data e preço de referência usados.

A experiência é mobile-first e não contém regras financeiras no React.

## Limites e preparação futura

A v1 não monitora mudanças, compara planos automaticamente, emite alertas,
rebalanceia, executa compras/vendas, movimenta dinheiro ou cria ações de Trading.
Os IDs, fingerprints e timestamps persistidos permitem que uma futura camada de
Continuous Autopilot compare planos A e B sem reinterpretar decisões históricas.
Trading V2 permanece isolado, `PAPER_ONLY`, com `speculative_capital = 0` e
`trading_dispatch = false`.
