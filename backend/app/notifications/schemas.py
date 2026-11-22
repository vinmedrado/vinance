from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


_PUSH_PROVIDER_HOSTS = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "web.push.apple.com",
}
_PUSH_PROVIDER_SUFFIXES = (
    ".push.services.mozilla.com",
    ".push.apple.com",
    ".notify.windows.com",
)


def validate_public_push_endpoint(value: str) -> str:
    """Restrict provider callbacks so subscriptions cannot become SSRF targets."""

    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    provider_host = host in _PUSH_PROVIDER_HOSTS or any(
        host.endswith(suffix) and host != suffix.removeprefix(".")
        for suffix in _PUSH_PROVIDER_SUFFIXES
    )
    if (
        parsed.scheme.lower() != "https"
        or not provider_host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or bool(parsed.fragment)
    ):
        raise ValueError("Endpoint Web Push deve pertencer a um provedor HTTPS suportado")
    return value


class PushSubscriptionKeys(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p256dh: str = Field(min_length=40, max_length=512)
    auth: str = Field(min_length=16, max_length=256)


class BrowserPushSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    endpoint: HttpUrl
    expiration_time: int | None = Field(default=None, alias="expirationTime")
    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def endpoint_must_be_public_push_provider(cls, value: HttpUrl) -> HttpUrl:
        validate_public_push_endpoint(str(value))
        return value


class PushSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    installation_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    subscription: BrowserPushSubscription


class NotificationCapabilities(BaseModel):
    web_push_enabled: bool
    vapid_public_key: str | None


class NotificationPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    push_enabled: bool
    account_events_enabled: bool
    household_invites_enabled: bool
    financial_alerts_enabled: bool
    analysis_updates_enabled: bool


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    push_enabled: bool | None = None
    account_events_enabled: bool | None = None
    household_invites_enabled: bool | None = None
    financial_alerts_enabled: bool | None = None
    analysis_updates_enabled: bool | None = None


class PushSubscriptionRead(BaseModel):
    id: str
    installation_id: str
    status: str
    created_at: datetime


class PushActionResult(BaseModel):
    status: str
    message: str
    queued: int = 0
