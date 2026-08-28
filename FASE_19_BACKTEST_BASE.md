# Fase 19 — Backtest Base + Validação Quantitativa

## Objetivo

Criar uma camada inicial de backtest para validar, de forma histórica e controlada, se os rankings baseados em `score_final` das tabelas `*_ml_features` apresentam coerência quantitativa. Esta fase não treina modelos, não cria XGBoost operacional, não cria LSTM/Prophet, não altera frontend, não altera providers e não gera recomendação definitiva de compra.

## Arquivos criados

- `backend/app/intelligence/backtest/__init__.py`
- `backend/app/intelligence/backtest/schemas.py`
- `backend/app/intelligence/backtest/metrics.py`
- `backend/app/intelligence/backtest/engine.py`
- `backend/app/intelligence/backtest/service.py`
- `backend/app/intelligence/backtest/router.py`
- `backend/tests/test_backtest_base_phase19.py`
- `FASE_19_BACKTEST_BASE.md`

## Arquivos alterados

- `backend/app/intelligence/router.py`
  - inclusão do subrouter `/api/v1/intelligence/backtest`.

Nenhum arquivo de frontend, providers, advisor, market scraping, migrations ou regras financeiras foi alterado.

## Métricas implementadas

Em `metrics.py`:

- `total_return`
- `annualized_return`
- `volatility`
- `sharpe_ratio`
- `max_drawdown`
- `win_rate`
- `hit_rate_top_n`

Todas as métricas aceitam séries vazias ou insuficientes e retornam `None` quando não há dados suficientes, evitando exceções indevidas.

## Premissas

- O backtest é calculado on-demand.
- Não há persistência de resultado nesta fase.
- Não há custos, impostos, slippage, corretagem ou spread.
- Não há alavancagem.
- Não há benchmark complexo ainda.
- A carteira simulada usa seleção top N por `score_final`.
- O score usado é heurístico/quantitativo da Fase 18, não ML treinado.

## Como evita lookahead bias

A engine usa apenas features com data menor ou igual à data de rebalanceamento. A entrada acontece apenas em preço posterior à data do sinal, nunca no mesmo instante usado para formar o ranking. O retorno futuro é calculado na janela definida por `holding_period_days`.

## Como usa `score_final`

Para cada data de rebalanceamento, o sistema busca o ranking disponível por `score_final` em `*_ml_features`, seleciona os maiores scores até `top_n` e calcula retorno futuro usando `asset_prices`.

## Endpoints criados

Prefixo autenticado:

- `POST /api/v1/intelligence/backtest/run`
- `GET /api/v1/intelligence/backtest/summary`

O endpoint `/run` recebe:

```json
{
  "market": "acoes",
  "start_date": "2024-01-01",
  "end_date": "2025-01-01",
  "holding_period_days": 90,
  "top_n": 5,
  "rebalance_frequency": "monthly"
}
```

E retorna parâmetros, métricas, warnings, tamanho da amostra e metodologia.

## Limitações

- Sem benchmark complexo.
- Sem persistência histórica dos resultados.
- Sem análise de custos/transações.
- Sem otimização de pesos.
- Sem treino de modelo.
- Sem validação walk-forward avançada.
- A primeira versão usa uma curva de capital simples baseada em trades fechados igualmente ponderados.

## Por que ML ainda não foi treinado

A base atual ainda precisa validar se as features e scores heurísticos têm alguma coerência histórica antes de alimentar qualquer modelo supervisionado. Treinar XGBoost, LSTM ou Prophet agora criaria risco de overfitting, falsa confiança e complexidade operacional antes da validação quantitativa mínima.

## Testes criados

- Métricas com série válida.
- Métricas com série vazia.
- `max_drawdown`.
- `sharpe_ratio` com volatilidade zero.
- Seleção top N por maior score.
- Entrada apenas após data do sinal.
- Ativo sem preço ignorado com warning.
- Metodologia deixa explícito que não há ML treinado.

## Validação executada

- `python -m compileall backend/app scripts workers`: OK.
- `pytest`: não executado integralmente no sandbox por ausência de dependências do ambiente, mas os testes da Fase 19 foram criados sem chamada externa.
- Backend startup: não executado no sandbox pelo mesmo motivo de dependências/runtime.

## Riscos remanescentes

- Métricas dependem da qualidade e completude de `asset_prices` e `*_ml_features`.
- Sem custos, o retorno pode parecer mais otimista do que seria na prática.
- Falhas de liquidez real ainda não são modeladas.
- Rebalanceamento mensal usa aproximação de 30 dias na engine base.

## Preparação para Fase 20

A Fase 19 deixa preparado:

- base de métricas quantitativas;
- engine sem lookahead óbvio;
- endpoints internos para validação;
- camada de serviço para consultar features/preços;
- base para futura persistência de resultados, benchmark e validação walk-forward.
