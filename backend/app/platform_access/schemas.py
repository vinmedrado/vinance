from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class AccessCapabilities(BaseModel):
    access_mode: str
    public_signup: bool = False
    bootstrap_available: bool
    invite_only: bool = True
    email_delivery_available: bool
    password_recovery_delivery_available: bool
    cloudflare_access_automation_available: bool


class CredentialRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)
    privacy_acknowledged: bool

    @model_validator(mode="after")
    def validate_credentials(self):
        if self.password != self.password_confirmation:
            raise ValueError("Password confirmation does not match")
        if not self.privacy_acknowledged:
            raise ValueError("Privacy acknowledgement is required")
        return self


class BootstrapRequest(CredentialRegistration):
    bootstrap_credential: str = Field(min_length=32, max_length=512)


class InvitationAcceptRequest(CredentialRegistration):
    token: str = Field(min_length=32, max_length=512)


class PlatformAccessProfile(BaseModel):
    is_platform_admin: bool


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email_normalized: EmailStr
    status: str
    delivery_status: str
    cloudflare_access_status: str
    expires_at: datetime
    accepted_at: datetime | None = None
    cancelled_at: datetime | None = None
    resend_count: int
    created_at: datetime


class InvitationIssued(BaseModel):
    invitation: InvitationRead
    registration_path: str
    manual_link_required: bool = True
    message: str


class PlatformUserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    is_active: bool
    is_platform_admin: bool
    created_at: datetime


class PasswordRecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class PasswordRecoveryAccepted(BaseModel):
    accepted: bool = True
    delivery_available: bool
    message: str


class PasswordResetComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.password_confirmation:
            raise ValueError("Password confirmation does not match")
        return self


class ManualPasswordResetIssued(BaseModel):
    reset_path: str
    expires_at: datetime
    message: str


class AccessActionResult(BaseModel):
    status: str
    message: str
