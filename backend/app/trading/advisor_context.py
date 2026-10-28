from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial_state import service as financial_state_service
from backend.trading.model_registry import get_registry

from . import repository, service
from .errors import TradingDomainError


TRADING_TERMS = (
    "trading",
    "paper trading",
    "conta paper",
    "ordem simulada",
    "posição simulada",
    "posicao simulada",
    "carteira simulada",
    "backtest",
    "drawdown",
    "p&l",
    "pnl",
    "btcusdt",
    "ethusdt",
    "bnbusdt",
    "solusdt",
    "xrpusdt",
    "qual modelo o vinance",
    "oportunidade hoje",
    "operação foi bloqueada",
    "operacao foi bloqueada",
    "ganhei ou perdi na simulação",
    "ganhei ou perdi na simulacao",
)


def is_trading_question(message: str) -> bool:
    lowered = message.casefold()
    return any(term in lowered for term in TRADING_TERMS)


def _select(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: item[field] for field in fields if item.get(field) is not None}


def _event_context(item: dict[str, Any]) -> dict[str, Any]:
    event = _select(item, ("event_type", "symbol", "created_at"))
    payload = item.get("event_payload")
    if isinstance(payload, dict):
        allowed = {
            "order_status", "quantity", "entry_price", "entry_fee", "exit_price",
            "realized_pnl", "fees", "paper_only", "status", "reason",
        }
        event["event_payload"] = {
            key: payload[key] for key in sorted(allowed) if key in payload
        }
    return event


async def build_trading_advisor_context(
    session: AsyncSession, *, user_id: int
) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    try:
        await repository.require_schema(session)
        household = await financial_state_service.get_default_household(
            session, user_id=user_id
        )
        budget = await service.get_risk_budget(
            session, user_id=user_id, household_id=household.id
        )
        account_row = await repository.get_account(session, owner_user_id=user_id)
        account = service._account_read(account_row) if account_row else None
        positions = await service.list_paper_positions(
            session, user_id=user_id, status="OPEN", limit=5, offset=0
        )
        opportunities = await service.list_opportunities(
            session, symbol=None, limit=5, offset=0
        )
        backtests = await service.list_backtests(session, limit=3, offset=0)
        events = await service.list_paper_events(
            session, user_id=user_id, limit=5, offset=0
        )
    except (TradingDomainError, financial_state_service.FinancialStateDomainError) as exc:
        warnings.append(f"Contexto de Trading indisponível: {exc}")
        return None, warnings

    try:
        model_health = get_registry().health()
    except RuntimeError:
        model_health = {
            "status": "REGISTRY_UNAVAILABLE",
            "paper_trading_ready": False,
            "active": 0,
            "candidates": 0,
        }

    context = {
        "mode": "PAPER_ONLY",
        "real_trading_allowed": False,
        "broker_execution": False,
        "financial_context": {
            "risk_budget_status": budget.risk_budget_status,
            "real_trading_capital": str(budget.real_trading_capital),
            "paper_simulation_allowed": budget.paper_simulation_allowed,
            "blocking_reasons": budget.blocking_reasons[:8],
        },
        "paper_account": (
            {
                "quote_asset": account.quote_asset,
                "virtual_balance": str(account.cash),
                "equity": str(account.equity),
                "realized_pnl": str(account.realized_pnl),
                "unrealized_pnl": str(account.unrealized_pnl),
                "max_drawdown": str(account.max_drawdown),
            }
            if account
            else None
        ),
        "open_positions": [
            _select(
                item,
                (
                    "symbol",
                    "side",
                    "quantity",
                    "average_entry_price",
                    "current_reference_price",
                    "unrealized_pnl",
                    "stop_price",
                    "target_price",
                ),
            )
            for item in positions.items[:5]
        ],
        "fresh_opportunities": [
            _select(
                item,
                (
                    "symbol",
                    "interval",
                    "signal_time",
                    "side",
                    "confidence",
                    "score",
                    "reference_price",
                    "stop_price",
                    "target_price",
                    "model_version",
                    "guardrail_status",
                    "reasons",
                ),
            )
            for item in opportunities.items[:5]
        ],
        "recent_events": [_event_context(item) for item in events.items[:5]],
        "backtest_summaries": [
            _select(
                item,
                (
                    "name",
                    "model",
                    "symbol",
                    "interval",
                    "period_start",
                    "period_end",
                    "trades",
                    "net_return",
                    "win_rate",
                    "profit_factor",
                    "max_drawdown",
                    "sharpe",
                    "costs_modeled",
                    "status",
                ),
            )
            for item in backtests.items[:3]
        ],
        "model_status": model_health,
        "limitations": [
            "Nenhum modelo está PAPER_ACTIVE enquanto Validation V2 não aprovar a promoção.",
            "Resultados simulados não autorizam uso de capital real.",
        ],
    }
    if not account:
        warnings.append("Conta de simulação ainda não iniciada.")
    if not opportunities.items:
        warnings.append("Nenhuma oportunidade Paper validada neste momento.")
    return context, warnings
