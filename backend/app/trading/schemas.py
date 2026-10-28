from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PaperOwnershipScope = Literal["PERSONAL"]
PaperOrderSide = Literal["BUY", "SELL"]
PaperOrderType = Literal["MARKET", "LIMIT"]


class TradingRiskBudgetRead(BaseModel):
    paper_only: Literal[True] = True
    real_trading_allowed: Literal[False] = False
    real_trading_capital: Decimal = Field(default=Decimal("0.00"), ge=0, le=0)
    paper_simulation_allowed: bool
    financial_status: str
    risk_budget_status: str
    protected_capital: Decimal | None = Field(default=None, ge=0)
    speculative_capital: Decimal = Field(default=Decimal("0.00"), ge=0, le=0)
    blocking_reasons: list[str]
    context_fingerprints: dict[str, str]
    household_id: int
    simulation_rules: dict[str, Any] = Field(default_factory=dict)


class PaperAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ownership_scope: PaperOwnershipScope = "PERSONAL"
    quote_asset: Literal["USDT"] = "USDT"
    initial_virtual_balance: Decimal = Field(
        default=Decimal("10000.00"), ge=Decimal("100.00"), le=Decimal("1000000.00")
    )
    paper_only: Literal[True] = True


class PaperAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    ownership_scope: PaperOwnershipScope
    status: str
    quote_asset: str
    initial_virtual_balance: Decimal
    cash: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    peak_equity: Decimal
    max_drawdown: Decimal
    ruleset_version: str
    paper_only: Literal[True]
    optimistic_version: int
    created_at: datetime
    updated_at: datetime


class PaperOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    signal_id: int | None = Field(default=None, ge=1)
    prediction_id: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    market: Literal["CRYPTO"] = "CRYPTO"
    interval: str = Field(default="5m", min_length=2, max_length=10)
    side: PaperOrderSide
    order_type: PaperOrderType = "MARKET"
    quantity: Decimal | None = Field(default=None, gt=0)
    notional: Decimal | None = Field(default=None, gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    paper_only: Literal[True] = True

    @model_validator(mode="after")
    def validate_size_and_type(self) -> "PaperOrderCreate":
        if self.quantity is None and self.notional is None:
            raise ValueError("quantity or notional is required")
        if self.quantity is not None and self.notional is not None:
            raise ValueError("provide quantity or notional, not both")
        if self.order_type == "LIMIT" and self.limit_price is None:
            raise ValueError("limit_price is required for LIMIT orders")
        if self.side == "SELL":
            raise ValueError(
                "opening short positions is not supported; close an existing simulated position instead"
            )
        return self


class IdempotentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    paper_only: Literal[True] = True


class PaperOrderRead(BaseModel):
    id: int
    paper_account_id: int
    owner_user_id: int
    idempotency_key: str
    signal_id: int | None
    prediction_id: str | None
    symbol: str
    market: str
    interval: str
    side: str
    order_type: str
    quantity: Decimal
    notional: Decimal
    reference_price: Decimal
    limit_price: Decimal | None
    stop_price: Decimal | None
    target_price: Decimal | None
    fee_paid: Decimal
    status: str
    model_version: str | None
    feature_version: str | None
    target_version: str | None
    risk_decision: str
    risk_snapshot: dict[str, Any]
    financial_fingerprints: dict[str, Any]
    paper_only: Literal[True]
    optimistic_version: int
    created_at: datetime
    updated_at: datetime
    filled_at: datetime | None
    cancelled_at: datetime | None


class PaperPositionRead(BaseModel):
    id: int
    paper_account_id: int
    owner_user_id: int
    symbol: str
    market: str
    interval: str
    side: str
    status: str
    quantity: Decimal
    average_entry_price: Decimal
    current_reference_price: Decimal
    entry_fee: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    stop_price: Decimal | None
    target_price: Decimal | None
    opening_order_id: int
    closing_order_id: int | None
    paper_only: Literal[True]
    optimistic_version: int
    opened_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class PaperEventRead(BaseModel):
    id: int
    owner_user_id: int
    paper_account_id: int
    event_type: str
    signal_id: int | None
    prediction_id: str | None
    order_id: int | None
    position_id: int | None
    symbol: str | None
    event_payload: dict[str, Any]
    decision_context: dict[str, Any]
    risk_context: dict[str, Any]
    correlation_id: str
    created_at: datetime


class TradingOpportunityRead(BaseModel):
    signal_id: int
    symbol: str
    market: Literal["CRYPTO"] = "CRYPTO"
    interval: str
    signal_time: datetime
    freshness: str
    side: str
    confidence: Decimal | None
    score: Decimal | None
    reference_price: Decimal | None
    stop_price: Decimal | None
    target_price: Decimal | None
    model_version: str
    feature_version: str | None
    target_version: str | None
    guardrail_status: str
    reasons: list[str]


class TradingSignalRead(BaseModel):
    id: int
    symbol: str
    interval: str
    signal_time: datetime
    model_version: str
    side: str
    probability: Decimal | None
    score: Decimal | None
    reason: dict[str, Any]
    created_at: datetime


class TradingBacktestRead(BaseModel):
    id: str
    name: str
    model: str | None = None
    symbol: str | None = None
    interval: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    trades: int | None = None
    gross_return: Decimal | None = None
    net_return: Decimal | None = None
    win_rate: Decimal | None = None
    profit_factor: Decimal | None = None
    max_drawdown: Decimal | None = None
    sharpe: Decimal | None = None
    fees: Decimal | None = None
    slippage: Decimal | None = None
    spread: Decimal | None = None
    costs_modeled: bool
    status: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]


class TradingModelRead(BaseModel):
    model_id: str
    version: str
    symbol: str
    interval: str
    target_version: str
    feature_version: str
    artifact_checksum: str
    created_at: datetime | None
    trained_until: datetime | None
    validation_status: str
    promotion_status: str
    metrics: dict[str, Any]


class TradingListResponse(BaseModel):
    items: list[Any]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class TradingOverviewRead(BaseModel):
    paper_only: Literal[True] = True
    product_status: str
    risk_budget: TradingRiskBudgetRead
    paper_account: PaperAccountRead | None
    counts: dict[str, int]
    performance: dict[str, Decimal]
    models: dict[str, Any]


class TradingHealthRead(BaseModel):
    status: str
    paper_only: Literal[True] = True
    schema_version: str | None
    schema_compatible: bool
    research_data_ready: bool
    model_registry_ready: bool
    paper_trading_ready: bool
    continuous_scheduler_enabled: Literal[False] = False
    warnings: list[str]
