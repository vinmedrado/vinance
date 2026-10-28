# Trading V2 — produto Paper e limites restantes

O antigo gap de API, ownership e persistência foi fechado pelo **Trading
Assistido V1**. O produto expõe `/trading` e `/api/v1/trading` somente em modo
`PAPER_ONLY`, com conta, ordens, posições e eventos persistentes por usuário.

## O que já existe

- conta Paper `PERSONAL`, owner-only e saldo explicitamente virtual em USDT;
- risk budget de leitura, derivado do contexto A1→A6 sem autorizar capital real;
- oportunidades apenas de modelos `PAPER_ACTIVE` e sinais atuais aprovados;
- ordens e posições simuladas, idempotentes, com custos/slippage do engine V2;
- backtests válidos, model registry, histórico explicável e contexto allowlisted
  para o Assistente financeiro;
- schema Trading externo, versionado e separado do Alembic principal.

## Limites intencionais

- `TRADING_REAL = FALSE` e não existe integração de corretora;
- `HOUSEHOLD_PAPER_WRITES = FALSE`; nem o OWNER do household lê o Paper
  pessoal de outro membro;
- nenhum modelo está automaticamente ativo. Validation V2 precisa fornecer
  evidência `paper_trading_ready=true` e a promoção é manual/auditável;
- a orquestração é somente `run-once`; nenhum scheduler Trading é registrado
  no Celery Beat;
- a produção pode permanecer honestamente sem oportunidades enquanto não
  houver dados de runtime e modelo promovido;
- marcação contínua de posições e automação Paper ficam para uma autorização
  posterior.

Esses limites impedem que pesquisa histórica seja apresentada como
oportunidade atual ou que simulação seja confundida com capital disponível.
