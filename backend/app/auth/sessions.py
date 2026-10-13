from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import AuthSession, User
from backend.app.auth.security import create_access_token, generate_refresh_token, hash_refresh_token
from backend.app.core.config import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def issue_session(session: AsyncSession, user: User) -> tuple[str, str]:
    refresh_token = generate_refresh_token()
    record = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(record)
    await session.commit()
    return create_access_token(user.email, session_id=record.id), refresh_token


async def rotate_session(session: AsyncSession, refresh_token: str) -> tuple[User, str, str] | None:
    now = utcnow()
    result = await session.execute(
        select(AuthSession)
        .where(
            AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .with_for_update()
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    user = await session.get(User, record.user_id)
    if user is None or not user.is_active:
        record.revoked_at = now
        await session.commit()
        return None
    replacement = generate_refresh_token()
    record.refresh_token_hash = hash_refresh_token(replacement)
    record.last_used_at = now
    record.expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    await session.commit()
    return user, create_access_token(user.email, session_id=record.id), replacement


async def revoke_by_refresh_token(session: AsyncSession, refresh_token: str | None) -> None:
    if not refresh_token:
        return
    await session.execute(
        update(AuthSession)
        .where(AuthSession.refresh_token_hash == hash_refresh_token(refresh_token), AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    await session.commit()


async def revoke_all_user_sessions(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def session_is_active(session: AsyncSession, session_id: str, user_id: int) -> bool:
    result = await session.execute(
        select(AuthSession.id).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utcnow(),
        )
    )
    return result.scalar_one_or_none() is not None
