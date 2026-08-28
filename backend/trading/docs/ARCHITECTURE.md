# Arquitetura

```text
Binance pública / outros provedores
              ↓
market_data -> candles -> PostgreSQL
              ↓
features -> targets
              ↓
models -> signals
              ↓
risk -> backtests -> paper_trading
              ↓
monitoring
```

A tabela `cripto_fundamentals` deve ser usada como contexto adicional: market cap, volume de 24 horas, variações agregadas e metadados. A fonte primária de treino intradiário deve ser `crypto_candles`.
