from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    upgrade_sql: tuple[str, ...]
    downgrade_sql: tuple[str, ...]
    destructive_down: bool = False


INITIAL_RESEARCH = Migration(
    version="0001_initial_research",
    name="initial Trading V2 research schema",
    upgrade_sql=(
        """
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
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_crypto_candles_symbol_interval_time ON crypto_candles (symbol, interval, open_time DESC)",
        """
        CREATE TABLE IF NOT EXISTS crypto_features (
            id BIGSERIAL PRIMARY KEY,
            candle_id BIGINT NOT NULL REFERENCES crypto_candles(id) ON DELETE CASCADE,
            feature_version VARCHAR(30) NOT NULL,
            features JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_crypto_feature UNIQUE (candle_id, feature_version)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_crypto_features_version ON crypto_features (feature_version)",
        """
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
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS trading_signals (
            id BIGSERIAL PRIMARY KEY,
            symbol VARCHAR(40) NOT NULL,
            interval VARCHAR(10) NOT NULL,
            signal_time TIMESTAMPTZ NOT NULL,
            model_version VARCHAR(80) NOT NULL,
            side VARCHAR(20) NOT NULL,
            probability NUMERIC(8, 6),
            score NUMERIC(12, 6),
            reason JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_trading_signals_side CHECK (
                side IN ('BUY', 'SELL', 'HOLD', 'BUY_CANDIDATE', 'AVOID')
            )
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_trading_signals_symbol_time ON trading_signals (symbol, signal_time DESC)",
        """
        CREATE TABLE IF NOT EXISTS backtest_runs (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            strategy_version VARCHAR(80) NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finished_at TIMESTAMPTZ,
            parameters JSONB NOT NULL,
            metrics JSONB,
            status VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
        )
        """,
        """
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
        )
        """,
    ),
    downgrade_sql=(
        "DROP TABLE IF EXISTS paper_trades",
        "DROP TABLE IF EXISTS backtest_runs",
        "DROP TABLE IF EXISTS trading_signals",
        "DROP TABLE IF EXISTS crypto_targets",
        "DROP TABLE IF EXISTS crypto_features",
        "DROP TABLE IF EXISTS crypto_candles",
    ),
    destructive_down=True,
)


ASSISTED_PAPER_V1 = Migration(
    version="0002_assisted_paper_v1",
    name="owner scoped assisted paper trading product",
    upgrade_sql=(
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS prediction_id VARCHAR(128)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS candle_id BIGINT REFERENCES crypto_candles(id) ON DELETE SET NULL",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS feature_version VARCHAR(30)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS target_version VARCHAR(30)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS target_name VARCHAR(120)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS reference_price NUMERIC(30, 12)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS stop_price NUMERIC(30, 12)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS target_price NUMERIC(30, 12)",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS freshness_expires_at TIMESTAMPTZ",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS guardrail_status VARCHAR(24) NOT NULL DEFAULT 'RESEARCH_ONLY'",
        "ALTER TABLE trading_signals ADD COLUMN IF NOT EXISTS paper_only BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS trading_signals_side_check",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_side",
        "ALTER TABLE trading_signals ALTER COLUMN side TYPE VARCHAR(20)",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_side CHECK (side IN ('BUY', 'SELL', 'HOLD', 'BUY_CANDIDATE', 'AVOID'))",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_reference_price CHECK (reference_price IS NULL OR reference_price > 0)",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_stop_price CHECK (stop_price IS NULL OR stop_price > 0)",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_target_price CHECK (target_price IS NULL OR target_price > 0)",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_guardrail CHECK (guardrail_status IN ('RESEARCH_ONLY', 'APPROVED', 'WARNING', 'BLOCKED'))",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_paper_only CHECK (paper_only IS TRUE)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_trading_signals_prediction_id ON trading_signals (prediction_id) WHERE prediction_id IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_trading_signals_current_paper ON trading_signals (freshness_expires_at DESC, symbol, interval) WHERE paper_only IS TRUE AND guardrail_status = 'APPROVED'",
        """
        CREATE TABLE IF NOT EXISTS trading_paper_accounts (
            id BIGSERIAL PRIMARY KEY,
            owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            ownership_scope VARCHAR(16) NOT NULL DEFAULT 'PERSONAL',
            status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            quote_asset VARCHAR(12) NOT NULL DEFAULT 'USDT',
            initial_virtual_balance NUMERIC(30, 12) NOT NULL,
            cash NUMERIC(30, 12) NOT NULL,
            equity NUMERIC(30, 12) NOT NULL,
            realized_pnl NUMERIC(30, 12) NOT NULL DEFAULT 0,
            unrealized_pnl NUMERIC(30, 12) NOT NULL DEFAULT 0,
            peak_equity NUMERIC(30, 12) NOT NULL,
            max_drawdown NUMERIC(18, 12) NOT NULL DEFAULT 0,
            ruleset_version VARCHAR(80) NOT NULL,
            paper_only BOOLEAN NOT NULL DEFAULT TRUE,
            optimistic_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_trading_paper_account_owner UNIQUE (owner_user_id),
            CONSTRAINT uq_trading_paper_account_id_owner UNIQUE (id, owner_user_id),
            CONSTRAINT ck_trading_paper_account_personal CHECK (ownership_scope = 'PERSONAL'),
            CONSTRAINT ck_trading_paper_account_status CHECK (status IN ('ACTIVE', 'SUSPENDED', 'CLOSED')),
            CONSTRAINT ck_trading_paper_account_quote CHECK (quote_asset = 'USDT'),
            CONSTRAINT ck_trading_paper_account_balances CHECK (initial_virtual_balance > 0 AND cash >= 0 AND equity >= 0 AND peak_equity >= equity AND max_drawdown BETWEEN 0 AND 1),
            CONSTRAINT ck_trading_paper_account_paper_only CHECK (paper_only IS TRUE),
            CONSTRAINT ck_trading_paper_account_version CHECK (optimistic_version >= 1)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_accounts_owner_status ON trading_paper_accounts (owner_user_id, status)",
        """
        CREATE TABLE IF NOT EXISTS trading_paper_orders (
            id BIGSERIAL PRIMARY KEY,
            paper_account_id BIGINT NOT NULL,
            owner_user_id INTEGER NOT NULL,
            idempotency_key VARCHAR(128) NOT NULL,
            request_fingerprint CHAR(64) NOT NULL,
            correlation_id VARCHAR(64) NOT NULL,
            signal_id BIGINT REFERENCES trading_signals(id) ON DELETE SET NULL,
            prediction_id VARCHAR(128),
            symbol VARCHAR(40) NOT NULL,
            market VARCHAR(20) NOT NULL,
            interval VARCHAR(10) NOT NULL,
            side VARCHAR(10) NOT NULL,
            order_type VARCHAR(16) NOT NULL,
            quantity NUMERIC(30, 12) NOT NULL,
            notional NUMERIC(30, 12) NOT NULL,
            reference_price NUMERIC(30, 12) NOT NULL,
            limit_price NUMERIC(30, 12),
            stop_price NUMERIC(30, 12),
            target_price NUMERIC(30, 12),
            fee_paid NUMERIC(30, 12) NOT NULL DEFAULT 0,
            status VARCHAR(20) NOT NULL,
            model_version VARCHAR(80),
            feature_version VARCHAR(30),
            target_version VARCHAR(30),
            risk_decision VARCHAR(40) NOT NULL,
            risk_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
            financial_fingerprints JSONB NOT NULL DEFAULT '{}'::jsonb,
            paper_only BOOLEAN NOT NULL DEFAULT TRUE,
            optimistic_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            filled_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            CONSTRAINT fk_trading_paper_order_account_owner FOREIGN KEY (paper_account_id, owner_user_id) REFERENCES trading_paper_accounts(id, owner_user_id) ON DELETE CASCADE,
            CONSTRAINT uq_trading_paper_order_id_owner UNIQUE (id, owner_user_id),
            CONSTRAINT uq_trading_paper_order_idempotency UNIQUE (paper_account_id, idempotency_key),
            CONSTRAINT ck_trading_paper_order_side CHECK (side IN ('BUY', 'SELL')),
            CONSTRAINT ck_trading_paper_order_type CHECK (order_type IN ('MARKET', 'LIMIT')),
            CONSTRAINT ck_trading_paper_order_status CHECK (status IN ('PENDING', 'FILLED', 'CANCELLED', 'REJECTED')),
            CONSTRAINT ck_trading_paper_order_values CHECK (quantity > 0 AND notional > 0 AND reference_price > 0 AND fee_paid >= 0 AND (limit_price IS NULL OR limit_price > 0) AND (stop_price IS NULL OR stop_price > 0) AND (target_price IS NULL OR target_price > 0)),
            CONSTRAINT ck_trading_paper_order_limit CHECK (order_type <> 'LIMIT' OR limit_price IS NOT NULL),
            CONSTRAINT ck_trading_paper_order_paper_only CHECK (paper_only IS TRUE),
            CONSTRAINT ck_trading_paper_order_version CHECK (optimistic_version >= 1)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_orders_owner_created ON trading_paper_orders (owner_user_id, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_orders_account_status ON trading_paper_orders (paper_account_id, status, created_at DESC)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_trading_paper_order_signal_once ON trading_paper_orders (paper_account_id, signal_id) WHERE signal_id IS NOT NULL AND status <> 'CANCELLED'",
        """
        CREATE TABLE IF NOT EXISTS trading_paper_positions (
            id BIGSERIAL PRIMARY KEY,
            paper_account_id BIGINT NOT NULL,
            owner_user_id INTEGER NOT NULL,
            symbol VARCHAR(40) NOT NULL,
            market VARCHAR(20) NOT NULL,
            interval VARCHAR(10) NOT NULL,
            side VARCHAR(10) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
            quantity NUMERIC(30, 12) NOT NULL,
            average_entry_price NUMERIC(30, 12) NOT NULL,
            current_reference_price NUMERIC(30, 12) NOT NULL,
            entry_fee NUMERIC(30, 12) NOT NULL DEFAULT 0,
            realized_pnl NUMERIC(30, 12) NOT NULL DEFAULT 0,
            unrealized_pnl NUMERIC(30, 12) NOT NULL DEFAULT 0,
            stop_price NUMERIC(30, 12),
            target_price NUMERIC(30, 12),
            opening_order_id BIGINT NOT NULL,
            closing_order_id BIGINT,
            paper_only BOOLEAN NOT NULL DEFAULT TRUE,
            optimistic_version INTEGER NOT NULL DEFAULT 1,
            opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            closed_at TIMESTAMPTZ,
            CONSTRAINT fk_trading_paper_position_account_owner FOREIGN KEY (paper_account_id, owner_user_id) REFERENCES trading_paper_accounts(id, owner_user_id) ON DELETE CASCADE,
            CONSTRAINT fk_trading_paper_position_open_order_owner FOREIGN KEY (opening_order_id, owner_user_id) REFERENCES trading_paper_orders(id, owner_user_id),
            CONSTRAINT fk_trading_paper_position_close_order_owner FOREIGN KEY (closing_order_id, owner_user_id) REFERENCES trading_paper_orders(id, owner_user_id),
            CONSTRAINT uq_trading_paper_position_open_order UNIQUE (opening_order_id),
            CONSTRAINT uq_trading_paper_position_id_owner UNIQUE (id, owner_user_id),
            CONSTRAINT ck_trading_paper_position_side CHECK (side = 'LONG'),
            CONSTRAINT ck_trading_paper_position_status CHECK (status IN ('OPEN', 'CLOSED')),
            CONSTRAINT ck_trading_paper_position_values CHECK (quantity > 0 AND average_entry_price > 0 AND current_reference_price > 0 AND entry_fee >= 0 AND (stop_price IS NULL OR stop_price > 0) AND (target_price IS NULL OR target_price > 0)),
            CONSTRAINT ck_trading_paper_position_close_state CHECK ((status = 'OPEN' AND closed_at IS NULL AND closing_order_id IS NULL) OR (status = 'CLOSED' AND closed_at IS NOT NULL AND closing_order_id IS NOT NULL)),
            CONSTRAINT ck_trading_paper_position_paper_only CHECK (paper_only IS TRUE),
            CONSTRAINT ck_trading_paper_position_version CHECK (optimistic_version >= 1)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_positions_owner_status ON trading_paper_positions (owner_user_id, status, opened_at DESC)",
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_positions_account_symbol ON trading_paper_positions (paper_account_id, symbol, status)",
        """
        CREATE TABLE IF NOT EXISTS trading_paper_events (
            id BIGSERIAL PRIMARY KEY,
            owner_user_id INTEGER NOT NULL,
            paper_account_id BIGINT NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            signal_id BIGINT REFERENCES trading_signals(id) ON DELETE SET NULL,
            prediction_id VARCHAR(128),
            order_id BIGINT,
            position_id BIGINT,
            symbol VARCHAR(40),
            event_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            decision_context JSONB NOT NULL DEFAULT '{}'::jsonb,
            risk_context JSONB NOT NULL DEFAULT '{}'::jsonb,
            correlation_id VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_trading_paper_event_account_owner FOREIGN KEY (paper_account_id, owner_user_id) REFERENCES trading_paper_accounts(id, owner_user_id) ON DELETE CASCADE,
            CONSTRAINT fk_trading_paper_event_order_owner FOREIGN KEY (order_id, owner_user_id) REFERENCES trading_paper_orders(id, owner_user_id),
            CONSTRAINT fk_trading_paper_event_position_owner FOREIGN KEY (position_id, owner_user_id) REFERENCES trading_paper_positions(id, owner_user_id)
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_events_owner_created ON trading_paper_events (owner_user_id, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_trading_paper_events_correlation ON trading_paper_events (correlation_id)",
        """
        CREATE OR REPLACE FUNCTION prevent_trading_paper_event_mutation()
        RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'trading_paper_events is append-only'; END; $$ LANGUAGE plpgsql
        """,
        "DROP TRIGGER IF EXISTS trg_trading_paper_events_immutable ON trading_paper_events",
        "CREATE TRIGGER trg_trading_paper_events_immutable BEFORE UPDATE OR DELETE ON trading_paper_events FOR EACH ROW EXECUTE FUNCTION prevent_trading_paper_event_mutation()",
    ),
    downgrade_sql=(
        "DROP TRIGGER IF EXISTS trg_trading_paper_events_immutable ON trading_paper_events",
        "DROP FUNCTION IF EXISTS prevent_trading_paper_event_mutation()",
        "DROP TABLE IF EXISTS trading_paper_events",
        "DROP TABLE IF EXISTS trading_paper_positions",
        "DROP TABLE IF EXISTS trading_paper_orders",
        "DROP TABLE IF EXISTS trading_paper_accounts",
        "DROP INDEX IF EXISTS ix_trading_signals_current_paper",
        "DROP INDEX IF EXISTS uq_trading_signals_prediction_id",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_side",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_paper_only",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_guardrail",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_target_price",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_stop_price",
        "ALTER TABLE trading_signals DROP CONSTRAINT IF EXISTS ck_trading_signals_reference_price",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS paper_only",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS guardrail_status",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS freshness_expires_at",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS target_price",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS stop_price",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS reference_price",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS target_name",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS target_version",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS feature_version",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS candle_id",
        "ALTER TABLE trading_signals DROP COLUMN IF EXISTS prediction_id",
        "ALTER TABLE trading_signals ALTER COLUMN side TYPE VARCHAR(10)",
        "ALTER TABLE trading_signals ADD CONSTRAINT ck_trading_signals_side CHECK (side IN ('BUY', 'SELL', 'HOLD'))",
    ),
    destructive_down=True,
)


MIGRATIONS: tuple[Migration, ...] = (INITIAL_RESEARCH, ASSISTED_PAPER_V1)
