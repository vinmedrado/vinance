from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.normalization import normalize_email
from backend.app.auth.schemas import UserCreate
from backend.app.auth.security import get_password_hash
from backend.app.auth.service import create_user_in_transaction, get_user_by_email
from backend.app.auth.sessions import revoke_all_user_sessions
from backend.app.core.config import settings
from backend.app.platform_access.models import (
    PasswordResetToken,
    PlatformAccessAuditEvent,
    PlatformAccessInvitation,
    PlatformAdmin,
    PlatformBootstrapState,
)
from backend.app.platform_access.schemas import (
    BootstrapRequest,
    InvitationAcceptRequest,
    PlatformUserRead,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_one_time_token() -> str:
    return secrets.token_urlsafe(48)


def hash_one_time_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token_digest(raw: str, expected_digest: str) -> bool:
    return hmac.compare_digest(hash_one_time_token(raw), expected_digest.strip().lower())


def _audit(
    session: AsyncSession,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    subject_user_id: int | None = None,
    invitation_id: str | None = None,
    correlation_id: str | None = None,
    metadata: dict[str, str | int | bool | None] | None = None,
) -> None:
    allowed = {"status", "source", "delivery_status", "cloudflare_access_status", "reason"}
    safe_metadata = {
        key: value
        for key, value in (metadata or {}).items()
        if key in allowed and isinstance(value, (str, int, bool, type(None)))
    }
    session.add(
        PlatformAccessAuditEvent(
            id=str(uuid4()),
            actor_user_id=actor_user_id,
            subject_user_id=subject_user_id,
            invitation_id=invitation_id,
            event_type=event_type,
            correlation_id=(correlation_id or str(uuid4()))[:64],
            metadata_json=safe_metadata,
        )
    )


async def access_capabilities(session: AsyncSession) -> dict[str, object]:
    state = await session.get(PlatformBootstrapState, 1)
    bootstrap_available = bool(
        state
        and state.completed_at is None
        and settings.access_mode == "INVITE_ONLY"
        and bool(settings.bootstrap_token_hash)
    )
    return {
        "access_mode": settings.access_mode,
        "public_signup": False,
        "bootstrap_available": bootstrap_available,
        "invite_only": True,
        # No delivery or Cloudflare provisioning provider exists yet. These
        # capabilities must remain honest even if an environment is
        # accidentally misconfigured; Settings also fails closed.
        "email_delivery_available": False,
        "password_recovery_delivery_available": False,
        "cloudflare_access_automation_available": False,
    }


async def bootstrap_platform(
    session: AsyncSession,
    payload: BootstrapRequest,
    *,
    correlation_id: str | None = None,
) -> User:
    expected = (settings.bootstrap_token_hash or "").strip().lower()
    if not expected or not verify_token_digest(payload.bootstrap_credential, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bootstrap authorization denied")

    state_result = await session.execute(
        select(PlatformBootstrapState).where(PlatformBootstrapState.id == 1).with_for_update()
    )
    state = state_result.scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Bootstrap is not provisioned")
    if state.completed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bootstrap is already complete")

    user_count = await session.scalar(select(func.count()).select_from(User))
    if int(user_count or 0) != 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap requires administrative reconciliation",
        )
    if await get_user_by_email(session, str(payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    user = await create_user_in_transaction(
        session,
        UserCreate(email=payload.email, password=payload.password, full_name=payload.full_name),
    )
    session.add(PlatformAdmin(user_id=user.id, status="ACTIVE", created_by_user_id=None))
    state.completed_at = utcnow()
    state.completed_by_user_id = user.id
    _audit(
        session,
        "PLATFORM_BOOTSTRAP_COMPLETED",
        actor_user_id=user.id,
        subject_user_id=user.id,
        correlation_id=correlation_id,
        metadata={"status": "COMPLETED", "source": "BROWSER_ONE_TIME_CREDENTIAL"},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def create_invitation(
    session: AsyncSession,
    *,
    actor_user_id: int,
    email: str,
    correlation_id: str | None = None,
) -> tuple[PlatformAccessInvitation, str]:
    normalized = normalize_email(email)
    if await get_user_by_email(session, normalized):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists")
    pending = await session.scalar(
        select(PlatformAccessInvitation).where(
            PlatformAccessInvitation.email_normalized == normalized,
            PlatformAccessInvitation.status == "PENDING",
        )
    )
    if pending is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A pending invitation already exists")

    raw_token = generate_one_time_token()
    invitation = PlatformAccessInvitation(
        id=str(uuid4()),
        email_normalized=normalized,
        token_hash=hash_one_time_token(raw_token),
        invited_by_user_id=actor_user_id,
        expires_at=utcnow() + timedelta(hours=settings.platform_invite_expire_hours),
        status="PENDING",
        delivery_status="MANUAL_LINK",
        cloudflare_access_status="PENDING_AUTHORIZATION",
    )
    session.add(invitation)
    # Establish the FK target before the immutable audit row; no ORM
    # relationship is needed between the two domains.
    await session.flush()
    _audit(
        session,
        "PLATFORM_INVITATION_CREATED",
        actor_user_id=actor_user_id,
        invitation_id=invitation.id,
        correlation_id=correlation_id,
        metadata={
            "delivery_status": invitation.delivery_status,
            "cloudflare_access_status": invitation.cloudflare_access_status,
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation conflicts with existing access") from exc
    await session.refresh(invitation)
    return invitation, raw_token


async def resend_invitation(
    session: AsyncSession,
    invitation_id: str,
    *,
    actor_user_id: int,
    correlation_id: str | None = None,
) -> tuple[PlatformAccessInvitation, str]:
    result = await session.execute(
        select(PlatformAccessInvitation)
        .where(PlatformAccessInvitation.id == invitation_id)
        .with_for_update()
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invitation is not pending")
    raw_token = generate_one_time_token()
    invitation.token_hash = hash_one_time_token(raw_token)
    invitation.expires_at = utcnow() + timedelta(hours=settings.platform_invite_expire_hours)
    invitation.last_resent_at = utcnow()
    invitation.resend_count += 1
    invitation.delivery_status = "MANUAL_LINK"
    _audit(
        session,
        "PLATFORM_INVITATION_ROTATED",
        actor_user_id=actor_user_id,
        invitation_id=invitation.id,
        correlation_id=correlation_id,
        metadata={"delivery_status": invitation.delivery_status},
    )
    await session.commit()
    await session.refresh(invitation)
    return invitation, raw_token


async def cancel_invitation(
    session: AsyncSession,
    invitation_id: str,
    *,
    actor_user_id: int,
    correlation_id: str | None = None,
) -> PlatformAccessInvitation:
    invitation = (
        await session.execute(
            select(PlatformAccessInvitation)
            .where(PlatformAccessInvitation.id == invitation_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "PENDING":
        raise HTTPException(status_code=409, detail="Invitation is not pending")
    invitation.status = "CANCELLED"
    invitation.cancelled_at = utcnow()
    _audit(
        session,
        "PLATFORM_INVITATION_CANCELLED",
        actor_user_id=actor_user_id,
        invitation_id=invitation.id,
        correlation_id=correlation_id,
        metadata={"status": "CANCELLED"},
    )
    await session.commit()
    await session.refresh(invitation)
    return invitation


async def accept_invitation(
    session: AsyncSession,
    payload: InvitationAcceptRequest,
    *,
    correlation_id: str | None = None,
) -> User:
    digest = hash_one_time_token(payload.token)
    invitation = (
        await session.execute(
            select(PlatformAccessInvitation)
            .where(PlatformAccessInvitation.token_hash == digest)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    now = utcnow()
    if invitation.status != "PENDING" or invitation.expires_at <= now:
        if invitation.status == "PENDING" and invitation.expires_at <= now:
            invitation.status = "EXPIRED"
            await session.commit()
        raise HTTPException(status_code=400, detail="Invalid or expired invitation")
    if invitation.email_normalized != normalize_email(str(payload.email)):
        raise HTTPException(status_code=403, detail="Invitation email does not match")
    if await get_user_by_email(session, str(payload.email)):
        raise HTTPException(status_code=409, detail="Account already exists")

    user = await create_user_in_transaction(
        session,
        UserCreate(email=payload.email, password=payload.password, full_name=payload.full_name),
    )
    invitation.status = "ACCEPTED"
    invitation.accepted_by_user_id = user.id
    invitation.accepted_at = now
    _audit(
        session,
        "PLATFORM_INVITATION_ACCEPTED",
        actor_user_id=user.id,
        subject_user_id=user.id,
        invitation_id=invitation.id,
        correlation_id=correlation_id,
        metadata={"status": "ACCEPTED"},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def list_platform_users(session: AsyncSession) -> list[PlatformUserRead]:
    rows = (
        await session.execute(
            select(User, PlatformAdmin.user_id)
            .outerjoin(
                PlatformAdmin,
                (PlatformAdmin.user_id == User.id) & (PlatformAdmin.status == "ACTIVE"),
            )
            .order_by(User.created_at.asc(), User.id.asc())
        )
    ).all()
    return [
        PlatformUserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            is_platform_admin=admin_user_id is not None,
            created_at=user.created_at,
        )
        for user, admin_user_id in rows
    ]


async def list_invitations(session: AsyncSession) -> list[PlatformAccessInvitation]:
    return list(
        (
            await session.scalars(
                select(PlatformAccessInvitation).order_by(
                    PlatformAccessInvitation.created_at.desc(),
                    PlatformAccessInvitation.id.desc(),
                )
            )
        ).all()
    )


async def set_user_active(
    session: AsyncSession,
    *,
    actor_user_id: int,
    target_user_id: int,
    active: bool,
    correlation_id: str | None = None,
) -> User:
    user = (
        await session.execute(select(User).where(User.id == target_user_id).with_for_update())
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    admin_rows = list(
        (
            await session.scalars(select(PlatformAdmin).where(PlatformAdmin.status == "ACTIVE").with_for_update())
        ).all()
    )
    target_admin = next((admin for admin in admin_rows if admin.user_id == target_user_id), None)
    if not active and target_admin is not None and len(admin_rows) <= 1:
        raise HTTPException(status_code=409, detail="The last platform administrator cannot be deactivated")

    user.is_active = active
    if not active:
        await revoke_all_user_sessions(session, user.id)
        from backend.app.notifications.service import revoke_user_push_access

        await revoke_user_push_access(session, user_id=user.id)
        if target_admin:
            target_admin.status = "REVOKED"
            target_admin.revoked_at = utcnow()
    _audit(
        session,
        "PLATFORM_USER_ACTIVATED" if active else "PLATFORM_USER_DEACTIVATED",
        actor_user_id=actor_user_id,
        subject_user_id=target_user_id,
        correlation_id=correlation_id,
        metadata={"status": "ACTIVE" if active else "INACTIVE"},
    )
    await session.commit()
    await session.refresh(user)
    return user


async def issue_manual_password_reset(
    session: AsyncSession,
    *,
    actor_user_id: int,
    target_user_id: int,
    correlation_id: str | None = None,
) -> tuple[str, datetime]:
    # Serialize reset-link rotation per user. Without this row lock, two
    # concurrent administrators can both revoke the same predecessor and each
    # commit a different active token.
    user = await session.get(User, target_user_id, with_for_update=True)
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="Active user not found")
    now = utcnow()
    await session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == target_user_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    raw_token = generate_one_time_token()
    expires_at = now + timedelta(minutes=settings.password_reset_expire_minutes)
    session.add(
        PasswordResetToken(
            id=str(uuid4()),
            user_id=target_user_id,
            token_hash=hash_one_time_token(raw_token),
            requested_by_user_id=actor_user_id,
            expires_at=expires_at,
        )
    )
    _audit(
        session,
        "PASSWORD_RESET_LINK_CREATED",
        actor_user_id=actor_user_id,
        subject_user_id=target_user_id,
        correlation_id=correlation_id,
        metadata={"delivery_status": "MANUAL_LINK"},
    )
    await session.commit()
    return raw_token, expires_at


async def complete_password_reset(
    session: AsyncSession,
    *,
    token: str,
    new_password: str,
    correlation_id: str | None = None,
) -> None:
    now = utcnow()
    record = (
        await session.execute(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == hash_one_time_token(token))
            .with_for_update()
        )
    ).scalar_one_or_none()
    if (
        record is None
        or record.used_at is not None
        or record.revoked_at is not None
        or record.expires_at <= now
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired password reset")
    user = await session.get(User, record.user_id, with_for_update=True)
    if user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired password reset")
    user.hashed_password = get_password_hash(new_password)
    record.used_at = now
    await revoke_all_user_sessions(session, user.id)
    _audit(
        session,
        "PASSWORD_RESET_COMPLETED",
        subject_user_id=user.id,
        correlation_id=correlation_id,
        metadata={"status": "COMPLETED"},
    )
    await session.commit()
