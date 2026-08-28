BEGIN;

CREATE TABLE IF NOT EXISTS crypto_candles (
    id BIGSERIAL PRIMARY KEY,
    exchange VARCHAR(40) NOT NULL,
    symbol VARCHAR(40) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ,
    open NUMERIC(30, 12) NOT NULL,
    high NUMERIC(30, 12) NOT NULL,
    low NUMERIC(30, 12) NOT NULL,
    close NUMERIC(30, 12) NOT NULL,
    volume NUMERIC(38, 12),
    quote_volume NUMERIC(38, 12),
    trades INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crypto_candle UNIQUE (exchange, symbol, interval, open_time),
    CONSTRAINT ck_crypto_candle_prices CHECK (
        open > 0 AND high > 0 AND low > 0 AND close > 0
        AND high >= GREATEST(open, close, low)
        AND low <= LEAST(open, close, high)
    )
);

CREATE INDEX IF NOT EXISTS ix_crypto_candles_symbol_interval_time
ON crypto_candles (symbol, interval, open_time DESC);

CREATE TABLE IF NOT EXISTS crypto_features (
    id BIGSERIAL PRIMARY KEY,
    candle_id BIGINT NOT NULL REFERENCES crypto_candles(id) ON DELETE CASCADE,
    feature_version VARCHAR(30) NOT NULL,
    features JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crypto_feature UNIQUE (candle_id, feature_version)
);

CREATE INDEX IF NOT EXISTS ix_crypto_features_version
ON crypto_features (feature_version);

CREATE TABLE IF NOT EXISTS crypto_targets (
    id BIGSERIAL PRIMARY KEY,
    candle_id BIGINT NOT NULL REFERENCES crypto_candles(id) ON DELETE CASCADE,
    target_name VARCHAR(80) NOT NULL,
    horizon_candles INTEGER NOT NULL,
    threshold_pct NUMERIC(12, 6),
    target_value NUMERIC(18, 8),
    target_class SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_crypto_target UNIQUE (candle_id, target_name, horizon_candles)
);

CREATE TABLE IF NOT EXISTS trading_signals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(40) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    signal_time TIMESTAMPTZ NOT NULL,
    model_version VARCHAR(80) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL', 'HOLD')),
    probability NUMERIC(8, 6),
    score NUMERIC(12, 6),
    reason JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_trading_signals_symbol_time
ON trading_signals (symbol, signal_time DESC);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    strategy_version VARCHAR(80) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    parameters JSONB NOT NULL,
    metrics JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
);

CREATE TABLE IF NOT EXISTS paper_trades (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trading_signals(id),
    symbol VARCHAR(40) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity NUMERIC(30, 12) NOT NULL,
    entry_price NUMERIC(30, 12) NOT NULL,
    exit_price NUMERIC(30, 12),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    fee_paid NUMERIC(30, 12) DEFAULT 0,
    pnl NUMERIC(30, 12),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
);

COMMIT;
