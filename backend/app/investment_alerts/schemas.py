from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.investment_alerts.rules import (
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MINIMUM_CONFIDENCE_DELTA,
    DEFAULT_MINIMUM_SCORE_DELTA,
    MAXIMUM_COOLDOWN_MINUTES,
    MINIMUM_ALLOWED_CONFIDENCE_DELTA,
    MINIMUM_ALLOWED_SCORE_DELTA,
    MINIMUM_COOLDOWN_MINUTES,
)


class SubscriptionPreferences(BaseModel):
    alert_on_action_change: bool = True
    alert_on_score_change: bool = True
    alert_on_confidence_change: bool = True
    alert_on_risk_change: bool = True
    alert_on_new_opportunity: bool = True
    minimum_score_delta: Decimal = Field(
        default=DEFAULT_MINIMUM_SCORE_DELTA,
        ge=MINIMUM_ALLOWED_SCORE_DELTA,
        le=Decimal("100"),
    )
    minimum_confidence_delta: Decimal = Field(
        default=DEFAULT_MINIMUM_CONFIDENCE_DELTA,
        ge=MINIMUM_ALLOWED_CONFIDENCE_DELTA,
        le=Decimal("100"),
    )
    cooldown_minutes: int = Field(
        default=DEFAULT_COOLDOWN_MINUTES,
        ge=MINIMUM_COOLDOWN_MINUTES,
        le=MAXIMUM_COOLDOWN_MINUTES,
    )


class SubscriptionCreate(SubscriptionPreferences):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.\-]+$")
    source_decision_id: str = Field(min_length=36, max_length=36)


class SubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    alert_on_action_change: bool | None = None
    alert_on_score_change: bool | None = None
    alert_on_confidence_change: bool | None = None
    alert_on_risk_change: bool | None = None
    alert_on_new_opportunity: bool | None = None
    minimum_score_delta: Decimal | None = Field(
        default=None, ge=MINIMUM_ALLOWED_SCORE_DELTA, le=Decimal("100")
    )
    minimum_confidence_delta: Decimal | None = Field(
        default=None, ge=MINIMUM_ALLOWED_CONFIDENCE_DELTA, le=Decimal("100")
    )
    cooldown_minutes: int | None = Field(
        default=None, ge=MINIMUM_COOLDOWN_MINUTES, le=MAXIMUM_COOLDOWN_MINUTES
    )


class SubscriptionResponse(SubscriptionPreferences):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset: str
    market: str
    budget: Decimal
    investor_profile: str
    source_decision_id: str
    enabled: bool
    rule_version: str
    created_at: datetime
    updated_at: datetime


class SubscriptionList(BaseModel):
    items: list[SubscriptionResponse]
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    limit: int = Field(ge=1)


class AlertItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    subscription_id: int | None = None
    decision_id: str
    asset: str
    alert_type: str
    severity: str
    delivery_channel: str
    message: str
    created_at: datetime
    read_at: datetime | None = None


class AlertDetail(AlertItem):
    previous_state: dict[str, Any]
    current_state: dict[str, Any]
    rule_version: str


class AlertPage(BaseModel):
    items: list[AlertItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    unread_count: int = Field(ge=0)


class AlertMetrics(BaseModel):
    active_subscriptions: int
    evaluations_performed: int
    alerts_generated: int
    cooldown_suppressed: int
    duplicates_prevented: int
    volume_suppressed: int
    errors: int
    unread_alerts: int
    by_type: dict[str, int]
