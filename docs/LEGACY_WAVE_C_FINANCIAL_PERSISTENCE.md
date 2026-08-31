# Onda C — consolidação da persistência financeira legada

## Resultado

A persistência financeira oficial continua sendo o módulo assíncrono
`backend.app.financial`, autenticado por usuário e sustentado pelas tabelas
PostgreSQL `users`, `incomes`, `expenses` e `financial_profiles`. A Onda C não
alterou schema nem dados.

Os leitores e gravadores SQLite antigos não faziam parte do call graph do
FastAPI, Celery ou frontend atuais. Foram aposentados o gravador isolado de
`despesas`, o ERP demonstrativo que criava tabelas em runtime, seus dois
serviços auxiliares e o leitor `personal_finance` que procurava um arquivo
SQLite local desabilitado. O cálculo de financiamento permanece disponível,
mas agora recebe somente valores explícitos já associados ao usuário pelo
chamador; não consulta banco local nem escolhe um usuário padrão.

## Inventário PostgreSQL read-only

A inspeção foi executada em transação `READ ONLY`, consultando apenas metadata,
constraints e contagens agregadas:

| Tabela canônica | Linhas | Ownership |
| --- | ---: | --- |
| `users` | 1 | PK `id` |
| `incomes` | 2 | `user_id` obrigatório, FK para `users.id` |
| `expenses` | 3 | `user_id` obrigatório, FK para `users.id` |
| `financial_profiles` | 1 | `user_id` obrigatório, único e FK para `users.id` |

Não foram encontradas linhas órfãs ou sem owner nas três tabelas financeiras.
As tabelas legadas `categorias`, `despesas`, `receitas`, `erp_*`,
`portfolio_*` e `tenants` não existem no PostgreSQL atual.

## Mapa de equivalência

| Contrato legado | Situação canônica |
| --- | --- |
| `despesas` | `expenses`, com schema diferente e ownership obrigatório |
| `receitas` | `incomes`, com schema diferente e ownership obrigatório |
| `categorias` | sem tabela própria; `expenses.category` é texto, não uma entidade equivalente |
| `erp_transactions` | pode representar renda ou despesa, mas não pode ser convertido sem owner e normalização semântica |
| `erp_budget_profiles` | `financial_profiles` cobre somente parte do contrato |
| `erp_goals` | `PRODUCT_GAP_GOALS` |
| `erp_planned_investments` | `PRODUCT_GAP_PORTFOLIO` |
| `portfolio_accounts`, `portfolio_transactions`, `portfolio_positions` | `PRODUCT_GAP_PORTFOLIO` |
| `tenants` | não existe tenancy canônica; ownership atual é individual via `users.id` |

Qualquer origem histórica ou planilha que venha a ser considerada no futuro é
`DATA_MIGRATION_REQUIRED` e `OWNERSHIP_MAPPING_REQUIRED`. É proibido escolher o
primeiro usuário, criar usuário implícito ou usar owner default.

## Lacunas de produto

- `PRODUCT_GAP_PORTFOLIO`: recomendações, backtests e paper trading não são uma
  carteira real do usuário. O VinanceOS atual não possui ledger canônico de
  contas, transações e posições reais.
- `PRODUCT_GAP_GOALS`: há motores de cálculo e modelos legados não montados,
  porém não há persistência moderna de objetivos financeiros no schema real.
- `PRODUCT_GAP_HOUSEHOLD`: não há household, cônjuge/membro nem ownership
  pessoal/compartilhado.
- Tenancy/organizations: modelos legados existem no código histórico, mas não
  estão montados no runtime oficial nem materializados no banco atual.

Essas lacunas são requisitos futuros e não foram implementadas nesta onda.
Também não devem ser confundidas com o futuro Autopilot.

## Tooling local preservado

`services/import_excel.py` permanece `MANTER_LOCAL`. As planilhas locais não
foram abertas, importadas, movidas, apagadas ou versionadas. O importador não é
referenciado pelo FastAPI nem pelo Celery e deverá ser tratado separadamente na
Onda E. Nenhum dado local pode ser importado sem mapeamento inequívoco de owner.

## Garantias da onda

- schema alterado: NÃO;
- migration criada: NÃO;
- dados alterados: NÃO;
- usuário default criado ou escolhido: NÃO;
- runtime assíncrono moderno alterado: NÃO;
- Recommendation Engine alterado: NÃO;
- dependência nova de SQLite ou `pg_compat`: NÃO.
