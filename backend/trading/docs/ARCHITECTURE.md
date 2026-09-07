# Arquitetura Trading V2

Binance pública / provedores -> market_data -> history_expansion_v2 -> PostgreSQL
-> feature_store -> target_engine -> ml_engine -> prediction_engine ->
backtesting_v2 -> research_v2 -> validation_v2 -> paper_trading_v2.

Trading V2 compartilha a conexão PostgreSQL canônica, mas possui schema operacional
explícito em storage/schema.sql. As tabelas crypto_candles, crypto_features,
crypto_targets, trading_signals, paper_trades e backtest_runs não pertencem ao
Base.metadata da aplicação. O filtro de ownership do Alembic impede que
autogenerate proponha removê-las.

A tabela cripto_fundamentals é contexto adicional. A fonte primária intradiária
continua sendo crypto_candles.

PAPER_ONLY é uma invariável: não existe stack operacional concorrente de V1 nem
execução real de corretora.
