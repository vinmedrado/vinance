# Capital Allocation v1

`capital-allocation-v1` transforma uma cadeia canônica de Financial State e
Financial Policy em valores mensais para cada prioridade. Ele não recalcula a
realidade financeira, não redefine a ordem da Policy, não seleciona ativos e não
executa movimentações.

```text
household-financial-state-v1
        +
financial-policy-v1
        -> capital-allocation-v1
```

## Responsabilidade e contrato

A entrada contém o Financial State exato e a Financial Policy derivada dele. O
data gate valida versões, household, snapshot, timestamp, fingerprint/evidência
da capacidade, qualidade, inconsistências, staleness crítico, moeda e a ordem
formal das prioridades. Divergência fecha a decisão como `BLOCKED`; um valor
ausente permanece `null`, nunca zero.

O período v1 é explicitamente `MONTHLY`, em `BRL`. O capital distribuível vem
somente de `financial_state.metrics.investment_capacity`, que o Autopilot 1 já
calcula depois do serviço mensal conhecido das dívidas. Renda, fluxo de caixa,
patrimônio líquido, imóveis, veículos e investimentos existentes são evidências,
mas não são tratados como dinheiro novo disponível.

O engine é puro, não consulta banco nem relógio e usa `evaluated_at` do State.
Para a mesma entrada e as mesmas regras, payload e fingerprints são idênticos.

## Ruleset congelado

`capital-allocation-rules-v1` centraliza período, moeda, precisão, modo de
arredondamento, buckets e catálogo de regras. Não há 70/20/10, 50/30/20 nem
percentuais universais. A precedência é a `priority_stack` já emitida pelo Policy
Engine:

1. completar informação crítica, quando necessário;
2. estabilizar fluxo de caixa;
3. reduzir passivos priorizados;
4. completar o gap da reserva definido pela Policy;
5. financiar goals prioritários;
6. classificar apenas o residual permitido como capital de investimento.

Uma entrada informacional nunca recebe dinheiro. Dívidas usam somente saldo,
parcela, custo e datas conhecidos; a taxa ausente não ganha valor arbitrário. A
parcela normal já foi considerada no State, portanto a alocação de dívida
representa redução adicional e não duplica o serviço mensal. Reserva consome
exclusivamente `reserve_policy.gap_amount`: o Allocation Engine não repete regras
de três a seis meses. Goals com gap e deadline usam o funding mensal produzido
pela Policy; sem deadline, nenhum prazo é inventado e o gap conhecido apenas
limita o valor possível do período.

## Status e buckets

- `BLOCKED`: State/Policy incompatível ou dado indispensável desconhecido.
- `CONSTRAINED`: capital zero, recuperação de caixa, prontidão bloqueada ou
  prioridade superior não atendida.
- `ACTIVE`: existe uma distribuição financeira válida sem residual elegível para
  investimento.
- `SURPLUS`: prioridades superiores foram atendidas e há residual elegível para
  a próxima fase.

Os buckets estruturais são `PROTECTED_CAPITAL`, `GOAL_CAPITAL`,
`INVESTMENT_CAPITAL` e `SPECULATIVE_CAPITAL`; itens apenas informativos usam
`INFORMATIONAL`. Em v1, capital especulativo é sempre `0.00`. O investment bucket
é somente um contrato de entrada futura do Autopilot 4: não contém classe,
produto, ativo específico ou ordem e não é enviado ao Trading V2.

## Ownership household

Prioridades `PERSONAL` só podem consumir a capacidade pessoal conhecida do mesmo
membro. Prioridades `HOUSEHOLD` consomem somente o pool consolidado que não foi
atribuído às capacidades pessoais, e esse residual só é inferido quando todos os
pools pessoais são conhecidos. Com qualquer pool pessoal desconhecido, nenhum
residual é promovido a `HOUSEHOLD`. Em um household de exatamente um membro, os
dois escopos reconciliam o mesmo pool somente quando as capacidades consolidada e
pessoal são idênticas; cada consumo reduz também o impacto individual. Quando os
valores diferem, apenas a diferença positiva comprovável forma o pool household.
Essa regra não transfere capital entre pessoas. Não existe
divisão 50/50 nem apropriação implícita em households com múltiplos membros.
`member_impacts` explica o efeito das prioridades pessoais/compartilhadas por
membro sem duplicar a decisão consolidada; o investment bucket agregado permanece
sem atribuição individual nesta fase.

Se, em um household com múltiplos membros, a soma das capacidades pessoais
conhecidas exceder a capacidade consolidada, o engine não escolhe qual membro
absorveu despesas compartilhadas. A decisão fecha como `BLOCKED` com
`UNRECONCILED_CAPITAL_OWNERSHIP` até que esse ownership possa ser reconciliado.

## Precisão e invariantes

Valores monetários são `Decimal`, quantizados em `0.01` e arredondados de forma
conservadora com `ROUND_DOWN`. A distribuição sequencial é reconciliada depois do
arredondamento e precisa satisfazer:

```text
allocated_amount >= 0
remaining_capital >= 0
sum(allocated_amount) <= allocatable_capital
sum(allocated_amount) + remaining_capital = allocatable_capital
speculative_capital = 0
```

Déficits aparecem como necessidade não financiada, nunca como alocação negativa.
Moedas incompatíveis bloqueiam o cálculo com
`CURRENCY_CONVERSION_MISSING`; esta versão não inventa FX nem adiciona provedor.

## Explicabilidade e auditoria

Cada item registra rank, bucket, alvo, ownership, valor solicitado, alocado,
necessidade restante, status, motivo e referências de evidência. A decisão também
guarda blockers, warnings, informação ausente e traces com ID da regra, versão,
valores observados e parâmetros. Os fingerprints cobrem State sem IDs de
persistência, Policy exata, ruleset e decisão completa.

As decisões congeladas formam a cadeia:

```text
financial_state_snapshots
        -> financial_policy_decisions
        -> capital_allocation_decisions
```

O payload histórico é imutável e é lido sem reexecutar engines futuros. FKs
compostas impedem associar decisões de households ou snapshots diferentes. O
header opcional `Idempotency-Key` é único por household; retries recuperam a mesma
cadeia. Triggers da migration canônica em PostgreSQL bloqueiam `UPDATE`,
`DELETE` e `TRUNCATE`, e não existe endpoint de edição.

## APIs

- `GET /api/v1/financial/households/{household_id}/capital-allocation`
- `GET /api/v1/financial/households/{household_id}/capital-allocation/from-policy/{policy_id}`
- `POST /api/v1/financial/households/{household_id}/capital-allocation/decisions`
- `GET /api/v1/financial/households/{household_id}/capital-allocation/history`
- `GET /api/v1/financial/households/{household_id}/capital-allocation/history/{allocation_id}`

Todas exigem autenticação, membership ativo e isolamento defensivo por household.
As respostas bem-sucedidas, inclusive o freeze, usam
`Cache-Control: private, no-store`.
O detalhe e o histórico devolvem a decisão congelada; o replay a partir de Policy
usa o State snapshot exato.

## Limites desta fase

Não há seleção de classes de ativos, percentuais por classe, Recommendation
Engine orchestration, compra, venda, rebalanceamento, corretora, PIX, Open
Finance, Trading Console ou capital entregue ao Trading. As seis tabelas Trading
V2 permanecem schema externo intencional ao Alembic principal; esta fase não as
lê nem as altera.
