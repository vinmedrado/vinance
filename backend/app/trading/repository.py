from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.trading.storage.migrate import LATEST_TRADING_SCHEMA_VERSION

from .errors import TradingNotFoundError, TradingSchemaNotReadyError


def _json(value: Mapping[str, Any] | list[Any] | None) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"), default=str)


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        raise TradingNotFoundError("trading resource not found")
    return dict(row)


async def schema_version(session: AsyncSession) -> str | None:
    try:
        result = await session.execute(
            text("SELECT version FROM trading_schema_version WHERE id = 1")
        )
        value = result.scalar_one_or_none()
        return str(value) if value else None
    except Exception:
        return None


async def require_schema(session: AsyncSession) -> str:
    version = await schema_version(session)
    if version != LATEST_TRADING_SCHEMA_VERSION:
        raise TradingSchemaNotReadyError(
            "Trading schema is not compatible with this application version"
        )
    return version


async def get_account(
    session: AsyncSession, *, owner_user_id: int, for_update: bool = False
) -> dict[str, Any] | None:
    suffix = " FOR UPDATE" if for_update else ""
    result = await session.execute(
        text(
            "SELECT * FROM trading_paper_accounts "
            "WHERE owner_user_id = :owner_user_id AND ownership_scope = 'PERSONAL'"
            + suffix
        ),
        {"owner_user_id": owner_user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def create_account(
    session: AsyncSession,
    *,
    owner_user_id: int,
    quote_asset: str,
    initial_virtual_balance: Decimal,
    ruleset_version: str,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            INSERT INTO trading_paper_accounts (
                owner_user_id, ownership_scope, status, quote_asset,
                initial_virtual_balance, cash, equity, realized_pnl,
                unrealized_pnl, peak_equity, max_drawdown,
                ruleset_version, paper_only
            ) VALUES (
                :owner_user_id, 'PERSONAL', 'ACTIVE', :quote_asset,
                :initial_virtual_balance, :initial_virtual_balance,
                :initial_virtual_balance, 0, 0, :initial_virtual_balance, 0,
                :ruleset_version, TRUE
            )
            ON CONFLICT (owner_user_id) DO NOTHING
            RETURNING *
            """
        ),
        {
            "owner_user_id": owner_user_id,
            "quote_asset": quote_asset,
            "initial_virtual_balance": initial_virtual_balance,
            "ruleset_version": ruleset_version,
        },
    )
    row = result.mappings().first()
    if row:
        created = dict(row)
        created["_created"] = True
        return created
    existing = await get_account(session, owner_user_id=owner_user_id, for_update=True)
    if existing is None:
        raise TradingNotFoundError("paper account could not be created")
    existing["_created"] = False
    return existing


async def account_counts(session: AsyncSession, *, owner_user_id: int) -> dict[str, int]:
    result = await session.execute(
        text(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM trading_paper_orders o
                    WHERE o.owner_user_id = :owner_user_id
                      AND o.status = 'PENDING'
                ) AS pending_orders,
                (
                    SELECT COUNT(*)
                    FROM trading_paper_positions p
                    WHERE p.owner_user_id = :owner_user_id
                      AND p.status = 'OPEN'
                ) AS open_positions
            """
        ),
        {"owner_user_id": owner_user_id},
    )
    row = result.mappings().one()
    return {
        "pending_orders": int(row["pending_orders"] or 0),
        "open_positions": int(row["open_positions"] or 0),
    }


async def get_order_by_idempotency(
    session: AsyncSession,
    *,
    paper_account_id: int,
    owner_user_id: int,
    idempotency_key: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT * FROM trading_paper_orders
            WHERE paper_account_id = :paper_account_id
              AND owner_user_id = :owner_user_id
              AND idempotency_key = :idempotency_key
            """
        ),
        {
            "paper_account_id": paper_account_id,
            "owner_user_id": owner_user_id,
            "idempotency_key": idempotency_key,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def insert_order(
    session: AsyncSession, *, values: Mapping[str, Any]
) -> dict[str, Any]:
    params = dict(values)
    params["risk_snapshot"] = _json(params.get("risk_snapshot"))
    params["financial_fingerprints"] = _json(params.get("financial_fingerprints"))
    result = await session.execute(
        text(
            """
            INSERT INTO trading_paper_orders (
                paper_account_id, owner_user_id, idempotency_key,
                request_fingerprint, correlation_id, signal_id, prediction_id,
                symbol, market, interval, side, order_type, quantity, notional,
                reference_price, limit_price, stop_price, target_price, status,
                model_version, feature_version, target_version, risk_decision,
                risk_snapshot, financial_fingerprints, fee_paid, paper_only, filled_at
            ) VALUES (
                :paper_account_id, :owner_user_id, :idempotency_key,
                :request_fingerprint, :correlation_id, :signal_id, :prediction_id,
                :symbol, :market, :interval, :side, :order_type, :quantity, :notional,
                :reference_price, :limit_price, :stop_price, :target_price, :status,
                :model_version, :feature_version, :target_version, :risk_decision,
                CAST(:risk_snapshot AS JSONB), CAST(:financial_fingerprints AS JSONB),
                :fee_paid, TRUE, :filled_at
            ) RETURNING *
            """
        ),
        params,
    )
    return _mapping(result.mappings().first())


async def get_order(
    session: AsyncSession,
    *,
    order_id: int,
    owner_user_id: int,
    for_update: bool = False,
) -> dict[str, Any] | None:
    suffix = " FOR UPDATE" if for_update else ""
    result = await session.execute(
        text(
            "SELECT * FROM trading_paper_orders "
            "WHERE id = :order_id AND owner_user_id = :owner_user_id" + suffix
        ),
        {"order_id": order_id, "owner_user_id": owner_user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_orders(
    session: AsyncSession,
    *,
    owner_user_id: int,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    status_filter = " AND status = :status" if status else ""
    params = {
        "owner_user_id": owner_user_id,
        "status": status,
        "limit": limit,
        "offset": offset,
    }
    total = int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM trading_paper_orders "
                    "WHERE owner_user_id = :owner_user_id" + status_filter
                ),
                params,
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        text(
            "SELECT * FROM trading_paper_orders "
            "WHERE owner_user_id = :owner_user_id"
            + status_filter
            + " ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()], total


async def cancel_order(
    session: AsyncSession, *, order_id: int, owner_user_id: int
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            UPDATE trading_paper_orders
            SET status = 'CANCELLED', cancelled_at = NOW(), updated_at = NOW(),
                optimistic_version = optimistic_version + 1
            WHERE id = :order_id AND owner_user_id = :owner_user_id
              AND status = 'PENDING' AND paper_only IS TRUE
            RETURNING *
            """
        ),
        {"order_id": order_id, "owner_user_id": owner_user_id},
    )
    return _mapping(result.mappings().first())


async def insert_position(
    session: AsyncSession, *, values: Mapping[str, Any]
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            INSERT INTO trading_paper_positions (
                paper_account_id, owner_user_id, symbol, market, interval, side,
                status, quantity, average_entry_price, current_reference_price,
                entry_fee, realized_pnl, unrealized_pnl, stop_price, target_price,
                opening_order_id, paper_only
            ) VALUES (
                :paper_account_id, :owner_user_id, :symbol, :market, :interval,
                :side, 'OPEN', :quantity, :average_entry_price,
                :current_reference_price, :entry_fee, 0, 0, :stop_price, :target_price,
                :opening_order_id, TRUE
            ) RETURNING *
            """
        ),
        dict(values),
    )
    return _mapping(result.mappings().first())


async def get_position(
    session: AsyncSession,
    *,
    position_id: int,
    owner_user_id: int,
    for_update: bool = False,
) -> dict[str, Any] | None:
    suffix = " FOR UPDATE" if for_update else ""
    result = await session.execute(
        text(
            "SELECT * FROM trading_paper_positions "
            "WHERE id = :position_id AND owner_user_id = :owner_user_id" + suffix
        ),
        {"position_id": position_id, "owner_user_id": owner_user_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_positions(
    session: AsyncSession,
    *,
    owner_user_id: int,
    status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    status_filter = " AND status = :status" if status else ""
    params = {
        "owner_user_id": owner_user_id,
        "status": status,
        "limit": limit,
        "offset": offset,
    }
    total = int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM trading_paper_positions "
                    "WHERE owner_user_id = :owner_user_id" + status_filter
                ),
                params,
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        text(
            "SELECT * FROM trading_paper_positions "
            "WHERE owner_user_id = :owner_user_id"
            + status_filter
            + " ORDER BY opened_at DESC, id DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()], total


async def close_position(
    session: AsyncSession,
    *,
    position_id: int,
    owner_user_id: int,
    closing_order_id: int,
    exit_price: Decimal,
    realized_pnl: Decimal,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            UPDATE trading_paper_positions
            SET status = 'CLOSED', current_reference_price = :exit_price,
                realized_pnl = :realized_pnl, unrealized_pnl = 0,
                closing_order_id = :closing_order_id, closed_at = NOW(),
                updated_at = NOW(), optimistic_version = optimistic_version + 1
            WHERE id = :position_id AND owner_user_id = :owner_user_id
              AND status = 'OPEN' AND paper_only IS TRUE
            RETURNING *
            """
        ),
        {
            "position_id": position_id,
            "owner_user_id": owner_user_id,
            "closing_order_id": closing_order_id,
            "exit_price": exit_price,
            "realized_pnl": realized_pnl,
        },
    )
    return _mapping(result.mappings().first())


async def update_account_after_open(
    session: AsyncSession,
    *,
    account_id: int,
    owner_user_id: int,
    debit: Decimal,
    entry_fee: Decimal,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            UPDATE trading_paper_accounts
            SET cash = cash - :debit, equity = equity - :entry_fee,
                max_drawdown = GREATEST(
                    max_drawdown,
                    CASE WHEN peak_equity > 0
                        THEN (peak_equity - (equity - :entry_fee)) / peak_equity
                        ELSE 0 END
                ),
                updated_at = NOW(), optimistic_version = optimistic_version + 1
            WHERE id = :account_id AND owner_user_id = :owner_user_id
              AND ownership_scope = 'PERSONAL' AND paper_only IS TRUE
              AND status = 'ACTIVE' AND cash >= :debit
            RETURNING *
            """
        ),
        {
            "account_id": account_id,
            "owner_user_id": owner_user_id,
            "debit": debit,
            "entry_fee": entry_fee,
        },
    )
    return _mapping(result.mappings().first())


async def update_account_after_close(
    session: AsyncSession,
    *,
    account_id: int,
    owner_user_id: int,
    proceeds_after_fee: Decimal,
    realized_pnl: Decimal,
) -> dict[str, Any]:
    result = await session.execute(
        text(
            """
            WITH account_value AS (
                SELECT
                    a.id,
                    a.cash + :proceeds_after_fee AS next_cash,
                    a.cash + :proceeds_after_fee + COALESCE((
                        SELECT SUM(p.current_reference_price * p.quantity)
                        FROM trading_paper_positions p
                        WHERE p.paper_account_id = a.id
                          AND p.owner_user_id = a.owner_user_id
                          AND p.status = 'OPEN'
                    ), 0) AS next_equity
                FROM trading_paper_accounts a
                WHERE a.id = :account_id
                  AND a.owner_user_id = :owner_user_id
                  AND a.ownership_scope = 'PERSONAL'
                  AND a.paper_only IS TRUE
                  AND a.status = 'ACTIVE'
                FOR UPDATE
            )
            UPDATE trading_paper_accounts a
            SET cash = value.next_cash,
                realized_pnl = a.realized_pnl + :realized_pnl,
                unrealized_pnl = COALESCE((
                    SELECT SUM((p.current_reference_price - p.average_entry_price) * p.quantity)
                    FROM trading_paper_positions p
                    WHERE p.paper_account_id = a.id AND p.owner_user_id = a.owner_user_id
                      AND p.status = 'OPEN'
                ), 0),
                equity = value.next_equity,
                peak_equity = GREATEST(a.peak_equity, value.next_equity),
                max_drawdown = GREATEST(
                    a.max_drawdown,
                    CASE WHEN GREATEST(a.peak_equity, value.next_equity) > 0
                        THEN (
                            GREATEST(a.peak_equity, value.next_equity)
                            - value.next_equity
                        ) / GREATEST(a.peak_equity, value.next_equity)
                        ELSE 0 END
                ),
                updated_at = NOW(), optimistic_version = a.optimistic_version + 1
            FROM account_value value
            WHERE a.id = value.id
            RETURNING a.*
            """
        ),
        {
            "account_id": account_id,
            "owner_user_id": owner_user_id,
            "proceeds_after_fee": proceeds_after_fee,
            "realized_pnl": realized_pnl,
        },
    )
    return _mapping(result.mappings().first())


async def insert_event(
    session: AsyncSession, *, values: Mapping[str, Any]
) -> dict[str, Any]:
    params = dict(values)
    for field in ("event_payload", "decision_context", "risk_context"):
        params[field] = _json(params.get(field))
    result = await session.execute(
        text(
            """
            INSERT INTO trading_paper_events (
                owner_user_id, paper_account_id, event_type, signal_id,
                prediction_id, order_id, position_id, symbol, event_payload,
                decision_context, risk_context, correlation_id
            ) VALUES (
                :owner_user_id, :paper_account_id, :event_type, :signal_id,
                :prediction_id, :order_id, :position_id, :symbol,
                CAST(:event_payload AS JSONB), CAST(:decision_context AS JSONB),
                CAST(:risk_context AS JSONB), :correlation_id
            ) RETURNING *
            """
        ),
        params,
    )
    return _mapping(result.mappings().first())


async def list_events(
    session: AsyncSession,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    params = {"owner_user_id": owner_user_id, "limit": limit, "offset": offset}
    total = int(
        (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM trading_paper_events "
                    "WHERE owner_user_id = :owner_user_id"
                ),
                params,
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        text(
            """
            SELECT * FROM trading_paper_events
            WHERE owner_user_id = :owner_user_id
            ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()], total


async def latest_reference_price(
    session: AsyncSession,
    *,
    symbol: str,
    interval: str,
    max_age_seconds: int,
) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            """
            SELECT id AS candle_id, symbol, interval, open_time, close
            FROM crypto_candles
            WHERE symbol = :symbol AND interval = :interval
              AND close > 0
              AND open_time >= NOW() - (:max_age_seconds * INTERVAL '1 second')
            ORDER BY open_time DESC, id DESC
            LIMIT 1
            """
        ),
        {
            "symbol": symbol,
            "interval": interval,
            "max_age_seconds": max_age_seconds,
        },
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def paper_risk_history(
    session: AsyncSession, *, paper_account_id: int, owner_user_id: int
) -> dict[str, Any]:
    executed = await session.execute(
        text(
            """
            SELECT s.symbol, s.interval, s.candle_id, o.model_version
            FROM trading_paper_orders o
            JOIN trading_signals s ON s.id = o.signal_id
            WHERE o.paper_account_id = :paper_account_id
              AND o.owner_user_id = :owner_user_id
              AND o.status = 'FILLED'
              AND o.side = 'BUY'
              AND s.candle_id IS NOT NULL
              AND o.model_version IS NOT NULL
            ORDER BY s.candle_id, o.id
            """
        ),
        {
            "paper_account_id": paper_account_id,
            "owner_user_id": owner_user_id,
        },
    )
    daily = await session.execute(
        text(
            """
            SELECT (p.closed_at AT TIME ZONE 'UTC')::date AS trading_day,
                   COALESCE(SUM(p.realized_pnl), 0) AS pnl
            FROM trading_paper_positions p
            WHERE p.paper_account_id = :paper_account_id
              AND p.owner_user_id = :owner_user_id
              AND p.status = 'CLOSED'
              AND p.closed_at IS NOT NULL
            GROUP BY (p.closed_at AT TIME ZONE 'UTC')::date
            ORDER BY trading_day
            """
        ),
        {
            "paper_account_id": paper_account_id,
            "owner_user_id": owner_user_id,
        },
    )
    return {
        "executed": [dict(row) for row in executed.mappings().all()],
        "daily": [dict(row) for row in daily.mappings().all()],
    }


async def get_signal(session: AsyncSession, *, signal_id: int) -> dict[str, Any] | None:
    result = await session.execute(
        text("SELECT * FROM trading_signals WHERE id = :signal_id"),
        {"signal_id": signal_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def list_signals(
    session: AsyncSession,
    *,
    opportunities_only: bool,
    symbol: str | None,
    limit: int,
    offset: int,
    active_models: list[tuple[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    filters = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset, "symbol": symbol}
    if symbol:
        filters.append("symbol = :symbol")
    if opportunities_only:
        filters.extend(
            [
                "paper_only IS TRUE",
                "guardrail_status = 'APPROVED'",
                "freshness_expires_at IS NOT NULL",
                "freshness_expires_at >= NOW()",
                "side IN ('BUY', 'BUY_CANDIDATE')",
                "prediction_id IS NOT NULL",
                "feature_version IS NOT NULL",
                "target_version IS NOT NULL",
                "target_name IS NOT NULL",
            ]
        )
        if not active_models:
            return [], 0
        active_filters: list[str] = []
        for index, (model_id, model_version) in enumerate(active_models):
            model_id_key = f"model_id_{index}"
            model_version_key = f"model_version_{index}"
            active_filters.append(
                f"(reason->>'model_id' = :{model_id_key} "
                f"AND model_version = :{model_version_key})"
            )
            params[model_id_key] = model_id
            params[model_version_key] = model_version
        filters.append("(" + " OR ".join(active_filters) + ")")
    where = " AND ".join(filters)
    total = int(
        (
            await session.execute(
                text(f"SELECT COUNT(*) FROM trading_signals WHERE {where}"), params
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        text(
            f"SELECT * FROM trading_signals WHERE {where} "
            "ORDER BY signal_time DESC, created_at DESC, id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        params,
    )
    return [dict(row) for row in result.mappings().all()], total


async def list_backtest_rows(
    session: AsyncSession, *, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    valid_where = (
        "UPPER(status) IN ('COMPLETED', 'SUCCESS', 'VALIDATED') "
        "AND metrics IS NOT NULL AND metrics <> '{}'::jsonb"
    )
    total = int(
        (
            await session.execute(
                text(f"SELECT COUNT(*) FROM backtest_runs WHERE {valid_where}")
            )
        ).scalar_one()
        or 0
    )
    result = await session.execute(
        text(
            """
            SELECT * FROM backtest_runs
            WHERE UPPER(status) IN ('COMPLETED', 'SUCCESS', 'VALIDATED')
              AND metrics IS NOT NULL AND metrics <> '{}'::jsonb
            ORDER BY started_at DESC, id DESC LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    )
    return [dict(row) for row in result.mappings().all()], total


async def get_backtest_row(session: AsyncSession, *, backtest_id: int) -> dict[str, Any] | None:
    result = await session.execute(
        text(
            "SELECT * FROM backtest_runs WHERE id = :backtest_id "
            "AND UPPER(status) IN ('COMPLETED', 'SUCCESS', 'VALIDATED') "
            "AND metrics IS NOT NULL AND metrics <> '{}'::jsonb"
        ),
        {"backtest_id": backtest_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None
