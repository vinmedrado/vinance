# Fixed Income V1

## Responsibility and boundaries

`fixed-income-v1` is the canonical adapter between real fixed-income products
stored by the market domain and `investment-orchestrator-v1`. It evaluates
facts about a product, suitability and the authorized budget; it does not
predict returns, execute an application or create a second recommendation
engine.

The only source of new investment capital is
`capital-allocation-v1.investment_bucket_amount`. Emergency reserves, goal
capital, income and existing assets are never reclassified as available cash.
`speculative_capital` remains zero and no value is dispatched to Trading V2.

## Supported products and sources

V1 supports sovereign bonds published by the official Tesouro Transparente
daily CSV (`precotaxatesourodireto.csv` in the official CKAN dataset). The
source identity and market date are frozen with every evaluated opportunity. A
provider failure is different from an empty dataset: the last known data
remains persisted with its original freshness and no product is silently
presented as current.

Supported subtype families are derived from the source data:

- Treasury Selic;
- Treasury Prefixado;
- Treasury IPCA+;
- Treasury Renda+;
- Treasury Educa+;
- other Treasury family, only when the official source supplies enough facts.

CDB, LCI and LCA are not supported in V1 because the repository has no
canonical real-data provider for current offers. They must not be synthesized
or inferred from the two historical `bootstrap_manual_partial` catalog rows.
Crypto investment also remains unsupported and separate from Crypto Trading.

## Canonical identity and catalog

Each market product has an immutable source identity independent of its
display name. The canonical key is the source plus its source product ID. A
product may reference `asset_catalog`, but the catalog describes the investable
universe; it is not proof that a user owns the product. User holdings continue
to live in `owned_assets`.

The persisted contract preserves nullable facts instead of converting absence
to zero. It can represent:

- source product ID, source and catalog reference;
- name, issuer, subtype, indexer and rate type;
- purchase/redemption rates and unit prices supplied by the source;
- maturity, liquidity type and liquidity days when known;
- minimum application, currency and market date;
- guarantee and tax treatment only when the source supports those facts;
- observation timestamp, active state and source metadata.

Treasury products are not marked as FGC-protected. Sovereign issuer context is
kept distinct from private deposit insurance.

## Provider lifecycle and freshness

The Celery market task fetches the official dataset, selects the latest
available market date, normalizes monetary values with `Decimal`, upserts the
batch transactionally and synchronizes deterministic catalog entries. Products
missing from a successful, non-empty latest snapshot may be deactivated. A
failed or empty fetch does not deactivate the last known good dataset. A
snapshot retaining less than 75% of the active universe is rejected as
potentially truncated before any deactivation; the previous snapshot remains
intact.

Freshness is evaluated by `fixed-income-rules-v1` with an explicit `as_of`.
The V1 threshold is five calendar days from the frozen `market_date`, matching
the daily-source contract while tolerating weekends and holidays. Historical
replay never calls the provider and never uses the wall clock implicitly. A
stale product cannot be promoted to `BUY`.

## Horizon, liquidity and maturity

The optional canonical profile field `investment_horizon_months` represents
the horizon of residual investment capital. It is not a goal deadline. `null`
means unknown and is never interpreted as long term or zero.

Known maturity and liquidity are compared with the known horizon. Products
whose suitability depends on holding to a date beyond the horizon are limited
or made to wait. When the horizon is unknown, duration-sensitive products are
not promoted; products with source-backed compatible liquidity may still be
evaluated subject to all other gates.

## Suitability, guardrails and ranking

The fixed-income adapter produces the same structured opportunity contract
consumed by the Investment Orchestrator. It records eligibility, action,
suitability, liquidity and maturity assessments, risk, budget, freshness,
evidence, warnings, blockers and rule traces.

Safety precedence is unchanged:

```text
BLOCKED guardrail -> never BUY
WARNING guardrail -> never silently promoted
APPROVED guardrail -> still requires every remaining gate
```

The rules cover at least inactive, expired and stale products; incompatible
currency; missing critical facts; inconsistent indexer/rate data; known
minimum application above budget; incompatible maturity or liquidity; and
profile mismatch. A nominally higher rate never wins by itself. Ranking is by
known suitability, liquidity, maturity fit, risk, data quality and budget fit.
Different indexers are not converted into a fabricated common future return.

## Budget and capital conservation

Fixed-income applications are amount-based unless the real source establishes
a meaningful unit contract. The engine does not manufacture integer lots.
Minimum application is enforced when known, using deterministic monetary
rounding and `Decimal`. This calculation reuses the canonical Budget Advisor
amount adapter; it is not a second budget engine.

The inherited invariants remain:

```text
sum(class allocations) <= investment budget
sum(product commitments per class) <= class allocation
suggested capital + remaining investment cash = investment budget
remaining investment cash >= 0
speculative capital = 0
trading dispatch = false
```

Capital can remain in cash. `NO_SUITABLE_OPPORTUNITY` is a valid result.

## Autopilot and household privacy

The Investment Orchestrator consumes fixed-income opportunities alongside the
already supported equity markets without fixed class percentages. Action Plan
and Continuous Autopilot keep using their generic frozen-decision contracts.
Material changes such as product expiration, staleness, eligibility or
guardrail/action transitions are visible without turning every small rate
movement into an alert.

Investor profile and horizon remain personal data. A shared-household decision
does not reveal or infer another member's raw profile, horizon or personal
portfolio. When the information required for a safe shared decision is not
available under the privacy contract, the decision fails closed or remains
limited.

## Frontend

`/investir` and the financial Autopilot present the structured backend result:
product, subtype, indexer/rate known at the decision time, maturity, liquidity,
minimum application, risk/guarantee facts, action, freshness and explanation.
React does not calculate suitability, ranking or allocation. Reference rates
and prices are historical decision inputs, not promised execution values or
future returns.

Renda fixa appears in `/investir` only through a frozen Autopilot
orchestration. The legacy manual market selector remains restricted to the
listed-asset Recommendation pipeline; adding `FIXED_INCOME` there would create
a competing evaluation path.

## Schema and downgrade

Migration `0026_fixed_income_v1` extends the existing canonical product table
and adds the nullable profile horizon. Its temporary BRL server default exists
only during upgrade backfill and is removed afterward to match SQLAlchemy
metadata. Downgrade is intentionally refused when canonical fixed-income rows
or a populated horizon exist, because silently discarding those facts would be
destructive; the downgrade test therefore runs only in an isolated empty
database.

## Explicit limitations

V1 does not provide CDB/LCI/LCA offers, homogeneous yield conversion, net-tax
return simulation, brokerage execution, Open Finance, automatic rebalancing,
Crypto Investment or Trading allocation. Adding any of those requires a real
source, explicit rules, versioned guardrails and a separately reviewed data
contract.
