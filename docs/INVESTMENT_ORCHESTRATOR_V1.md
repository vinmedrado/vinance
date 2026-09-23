# Investment Orchestrator V1

## Responsabilidade e fronteiras

`investment-orchestrator-v1` transforma exclusivamente o capital autorizado por `capital-allocation-v1` em uma estratégia de investimento explicável. A cadeia canônica é:

```text
household-financial-state-v1
  -> financial-policy-v1
  -> capital-allocation-v1.investment_bucket_amount
  -> investment-orchestrator-v1
```

O Orchestrator não recalcula situação financeira, prioridades nem capacidade de investimento. Também não cria um Recommendation Engine paralelo: ele reutiliza catálogo, scores, Investor Profile Advisor, Budget Advisor, Trend & Momentum, explanations e guardrails existentes.

A v1 não compra, vende, rebalanceia, movimenta dinheiro nem envia capital ao Trading. `speculative_capital` é sempre `0.00` e `trading_dispatch` é sempre `false`.

## Investment gate

Antes de consultar mercado, o engine valida:

- versões e fingerprints da cadeia State -> Policy -> Allocation, incluindo a comparação do Financial State atual com `capital_allocation.input_fingerprint`;
- mesmo household e, em decisões congeladas, os mesmos IDs de State e Policy;
- `investment_bucket_amount > 0` e conservação do Autopilot 3;
- `investment_readiness` e status da Capital Allocation;
- qualidade e confidence do Financial State;
- moeda BRL sem conversão FX inventada;
- perfil explícito de todos os membros ativos.

Estados formais:

- `BLOCKED`: cadeia, autorização financeira, moeda, perfil ou dados críticos inválidos;
- `LIMITED`: existe sugestão financiável, mas limitações conhecidas permanecem;
- `ACTIVE`: capital autorizado e oportunidade compatível sem limitação material conhecida;
- `NO_SUITABLE_OPPORTUNITY`: há capital autorizado, mas nenhuma oportunidade passa pelos critérios atuais. Todo o valor permanece em caixa.

Carteira ausente é `UNKNOWN`, nunca carteira zerada. O modelo atual não possui campo canônico de horizonte; sua ausência é registrada como `INVESTMENT_HORIZON_UNKNOWN` e limita a decisão, sem assumir longo prazo.

## Classes e perfil

A v1 considera apenas classes com pipeline canônico completo:

- `ACOES`;
- `FII`;
- `ETF`;
- `BDR`.

`FIXED_INCOME` e `CRYPTO` são expostas como `UNKNOWN`, pois ainda não possuem neste fluxo a mesma cadeia de catálogo, score, preço e guardrail. Isso não declara essas classes ruins; declara apenas que a infraestrutura v1 não consegue avaliá-las com qualidade equivalente.

O perfil é lido de `financial_profiles.risk_profile` e normalizado para o contrato do Investor Profile Advisor. Perfil ausente ou inconsistente bloqueia a avaliação. Em household com perfis diferentes, a v1 usa explicitamente o perfil mais conservador e registra warning; não presume que os membros tenham o mesmo risco.

## Mercado, Recommendation Engine e guardrails

Para cada mercado, o adaptador seleciona o snapshot mais recente em que score e guardrail canônicos coincidem por ticker, mercado, data e fonte. Candidatos sem guardrail exato são descartados. O contexto congelado registra:

- IDs, fontes, timestamps e metadata de score, guardrail e trend;
- preço de referência e sua fonte;
- recommendation score, risco, trend, momentum e confidence disponíveis;
- score de liquidez nullable, preservando ausência como desconhecida;
- freshness e falhas parciais por classe.

Dados com mais de sete dias são `STALE`. Preço, recommendation score ou liquidez ausentes nunca viram zero ou valor neutro.

Precedência de segurança:

- guardrail `BLOCKED` -> `AVOID`;
- guardrail `WARNING` -> `WAIT`;
- guardrail `APPROVED` ainda exige freshness, preço, score, liquidez e risco compatível;
- conflito sempre é normalizado em favor da segurança.

O Budget Advisor calcula possibilidades de quantidade dentro do orçamento. Seus itens são alternativas: a v1 compromete no máximo uma oportunidade por classe para não gastar o mesmo capital duas vezes.
As oportunidades finais são ranqueadas globalmente por ação segura, recommendation score e desempates determinísticos; a ordem fixa dos mercados nunca define o ranking.

## Classe, capital e conservação

Não existem percentuais universais por classe. Quando mais de uma classe possui oportunidade elegível, o budget por classe deriva da força relativa dos recommendation scores canônicos do snapshot congelado.

Todos os valores usam `Decimal`, centavos e `ROUND_DOWN`. As invariantes são:

```text
sum(class_allocations) <= investment_budget
sum(candidate commitments per class) <= class allocation
suggested_capital <= investment_budget
suggested_capital + remaining_investment_cash = investment_budget
speculative_capital = 0
trading_dispatch = false
```

Se uma unidade não couber no budget da classe, a ação vira `WAIT`. Sobra nunca é reinjetada silenciosamente em outra classe. Se nenhuma oportunidade for adequada, o resultado formal é manter o capital em caixa.

## Portfolio awareness

`owned_assets` é a fonte de posições pertencentes ao usuário/household; `asset_catalog` é apenas o universo global. Com posições conhecidas, o engine calcula exposição por mercado. Exposição acima de 50% torna novos aportes naquela mesma classe inelegíveis nesta v1. Valores, moeda ou vínculo de catálogo ausentes tornam a carteira `PARTIAL`. Posições fora de BRL sem FX canônico geram `currency_conversion_missing`; se nenhuma posição puder ser comparada, o total permanece `null`, enquanto um zero BRL realmente informado continua `0.00`.

Ownership pessoal e household permanecem congelados no Financial State. O Orchestrator não transfere capital entre membros nem presume divisão 50/50.

## Persistência, replay e idempotência

`investment_orchestration_decisions` guarda a decisão imutável e referencia exatamente:

- `financial_state_snapshot_id`;
- `financial_policy_decision_id`;
- `capital_allocation_decision_id`;
- household;
- budget autorizado pelo Autopilot 3.

Uma FK composta impede vincular uma decisão a outra cadeia ou a outro budget. Constraints garantem não negatividade, conservação e capital especulativo zero. Triggers PostgreSQL rejeitam `UPDATE`, `DELETE` e `TRUNCATE`.

O payload congela perfil, carteira, mercado, oportunidades, evidências e rule traces. Fingerprints independentes identificam State, Policy, Allocation, mercado, ruleset e decisão. Leitura histórica valida campos indexados e fingerprint e nunca consulta mercado atual.

`Idempotency-Key` é único por household. Retries retornam a mesma decisão. Também existe unicidade por Allocation + versões do engine/ruleset.

## API

Endpoints autenticados sob `/api/v1/financial/households/{household_id}`:

- `GET /investment-orchestration`;
- `GET /investment-orchestration/from-allocation/{allocation_id}`;
- `POST /investment-orchestration/decisions`;
- `GET /investment-orchestration/history`;
- `GET /investment-orchestration/history/{orchestration_id}`.

Todos exigem membership ativo, usam isolamento por household, 404 defensivo e `Cache-Control: private, no-store`.

## Experiência

Na área financeira, “Como investir este valor” apresenta budget autorizado, estratégia por classe, oportunidades, ações, bloqueios e caixa preservado. `/investir` continua sendo a central especializada; o Autopilot fornece contexto somente leitura por household/decision, sem criar uma segunda central ou executar ordens.

## Limites e evolução futura

A v1 não implementa produtos de renda fixa, cripto, câmbio, otimização de carteira, lotes inventados, corretora, Open Finance, execução, rebalanceamento, Continuous Autopilot ou Trading allocation. A próxima camada poderá consumir a decisão congelada para construir um Action Plan. Qualquer integração futura com Trading exigirá bucket especulativo explícito, autorização própria e contrato separado; o Trading V2 permanece isolado e `PAPER_ONLY`.
