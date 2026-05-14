from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from backend.app.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    plan = Column(String(40), nullable=False, default="free")
    subscription_status = Column(String(40), nullable=False, default="trialing")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    # compatibility columns kept nullable so old code/migrations do not break if referenced.
    tenant_id = Column(String(36), nullable=True, index=True)
    role = Column(String(80), nullable=True)
    plan = Column(String(40), nullable=True)


EnterpriseUser = User


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Permission(Base):
    __tablename__ = "permissions"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id = Column(Integer, primary_key=True)
    role_name = Column(String(80), nullable=False, index=True)
    permission_name = Column(String(120), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("role_name", "permission_name", name="uq_role_permission"),)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(80), nullable=False, default="member")
    is_active = Column(Boolean, nullable=False, default=True)
    invited_by = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member_user"),)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(36), nullable=False, index=True)
    plan = Column(String(40), nullable=False, default="free")
    status = Column(String(40), nullable=False, default="trialing")
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TenantSetting(Base):
    __tablename__ = "tenant_settings"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(36), nullable=False, index=True)
    key = Column(String(120), nullable=False)
    value_json = Column(Text, nullable=True)
    updated_by = Column(String(36), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_tenant_setting_key"),)


class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    refresh_token_hash = Column(String(128), nullable=False, unique=True)
    ip_address = Column(String(80), nullable=True)
    user_agent = Column(String(500), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(String(36), primary_key=True)
    organization_id = Column(String(36), nullable=True, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    replaced_by_hash = Column(String(128), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    token_hash = Column(String(128), nullable=False, unique=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(120), nullable=False, index=True)
    entity_type = Column(String(120), nullable=True, index=True)
    entity_id = Column(String(120), nullable=True)
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    ip_address = Column(String(80), nullable=True)
    user_agent = Column(String(500), nullable=True)
    request_id = Column(String(80), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class EnterpriseJob(Base):
    __tablename__ = "enterprise_jobs"
    id = Column(Integer, primary_key=True)
    organization_id = Column(String(36), nullable=False, index=True)
    created_by = Column(String(36), nullable=True, index=True)
    job_type = Column(String(120), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="queued", index=True)
    priority = Column(Integer, nullable=False, default=100)
    parameters_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (Index("ix_enterprise_jobs_org_status_priority", "organization_id", "status", "priority"),)
