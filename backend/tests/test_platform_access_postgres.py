from __future__ import annotations

import asyncio
from datetime import timedelta
import os

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.auth.models import AuthSession, User
from backend.app.auth.sessions import issue_session
from backend.app.core.config import settings
from backend.app.financial_state.models import Household, HouseholdMember
from backend.app.platform_access.dependencies import is_platform_admin
from backend.app.platform_access.models import (
    PasswordResetToken,
    PlatformAccessAuditEvent,
    PlatformAccessInvitation,
    PlatformAdmin,
    PlatformBootstrapState,
)
from backend.app.platform_access.schemas import BootstrapRequest, InvitationAcceptRequest
from backend.app.platform_access.service import (
    accept_invitation,
    bootstrap_platform,
    cancel_invitation,
    complete_password_reset,
    create_invitation,
    hash_one_time_token,
    issue_manual_password_reset,
    set_user_active,
    utcnow,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
]


@pytest_asyncio.fixture
async def session_factory(monkeypatch):
    assert TEST_DATABASE_URL is not None
    assert "test" in TEST_DATABASE_URL.lower()
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        # The isolated canonical schema intentionally protects immutable
        # decision snapshots with triggers. Test cleanup runs as the dedicated
        # test owner and temporarily suppresses triggers only around TRUNCATE.
        await connection.execute(text("SET LOCAL session_replication_role = 'replica'"))
        await connection.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await connection.execute(text("SET LOCAL session_replication_role = 'origin'"))
        await connection.execute(
            text(
                "INSERT INTO platform_bootstrap_state (id, completed_at, completed_by_user_id) "
                "VALUES (1, NULL, NULL) ON CONFLICT (id) DO UPDATE SET "
                "completed_at = NULL, completed_by_user_id = NULL"
            )
        )
    monkeypatch.setattr(settings, "access_mode", "INVITE_ONLY")
    yield factory
    await engine.dispose()


def _bootstrap_payload(email: str, token: str) -> BootstrapRequest:
    return BootstrapRequest(
        full_name="Administrador Vinance",
        email=email,
        password="senha-forte-para-testes",
        password_confirmation="senha-forte-para-testes",
        privacy_acknowledged=True,
        bootstrap_credential=token,
    )


def _invite_payload(email: str, token: str) -> InvitationAcceptRequest:
    return InvitationAcceptRequest(
        full_name="Pessoa Convidada",
        email=email,
        password="outra-senha-forte-testes",
        password_confirmation="outra-senha-forte-testes",
        privacy_acknowledged=True,
        token=token,
    )


async def _bootstrap(factory, monkeypatch, *, email: str = "admin@example.com") -> User:
    token = "bootstrap-credential-with-more-than-thirty-two-characters"
    monkeypatch.setattr(settings, "bootstrap_token_hash", hash_one_time_token(token))
    async with factory() as session:
        return await bootstrap_platform(session, _bootstrap_payload(email, token))


async def test_bootstrap_creates_isolated_personal_owner_and_platform_admin(
    session_factory, monkeypatch
) -> None:
    user = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as verify:
        state = await verify.get(PlatformBootstrapState, 1)
        household = await verify.scalar(
            select(Household).where(
                Household.created_by_user_id == user.id,
                Household.household_type == "PERSONAL",
            )
        )
        member = await verify.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household.id,
                HouseholdMember.user_id == user.id,
            )
        )
        assert state is not None and state.completed_by_user_id == user.id
        assert household is not None
        assert member is not None and member.role == "OWNER"
        assert await is_platform_admin(verify, user.id) is True
        assert await verify.scalar(select(PlatformAccessAuditEvent.event_type)) == "PLATFORM_BOOTSTRAP_COMPLETED"


async def test_bootstrap_rejects_invalid_one_time_credential(
    session_factory, monkeypatch
) -> None:
    monkeypatch.setattr(
        settings,
        "bootstrap_token_hash",
        hash_one_time_token("the-real-bootstrap-credential-is-long-enough"),
    )
    async with session_factory() as session:
        with pytest.raises(HTTPException) as rejected:
            await bootstrap_platform(
                session,
                _bootstrap_payload(
                    "attacker@example.com",
                    "a-different-bootstrap-credential-long-enough",
                ),
            )
        assert rejected.value.status_code == 403
        await session.rollback()
    async with session_factory() as verify:
        assert await verify.scalar(select(text("count(*)")).select_from(User)) == 0


async def test_bootstrap_is_atomic_under_concurrency(session_factory, monkeypatch) -> None:
    token = "bootstrap-credential-with-more-than-thirty-two-characters"
    monkeypatch.setattr(settings, "bootstrap_token_hash", hash_one_time_token(token))

    async def attempt(email: str):
        async with session_factory() as session:
            try:
                user = await bootstrap_platform(session, _bootstrap_payload(email, token))
                return ("created", user.email)
            except HTTPException as exc:
                await session.rollback()
                return ("rejected", exc.status_code)

    results = await asyncio.gather(attempt("first@example.com"), attempt("second@example.com"))
    assert sorted(item[0] for item in results) == ["created", "rejected"]
    async with session_factory() as verify:
        assert await verify.scalar(select(text("count(*)")).select_from(User)) == 1
        assert await verify.scalar(select(text("count(*)")).select_from(PlatformAdmin)) == 1


async def test_household_owner_is_not_implicitly_platform_admin(session_factory, monkeypatch) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        invitation, raw = await create_invitation(
            session, actor_user_id=admin.id, email="friend@example.com"
        )
    async with session_factory() as session:
        friend = await accept_invitation(session, _invite_payload("friend@example.com", raw))
    async with session_factory() as verify:
        assert await is_platform_admin(verify, friend.id) is False
        membership = await verify.scalar(
            select(HouseholdMember).where(HouseholdMember.user_id == friend.id)
        )
        assert membership is not None and membership.role == "OWNER"
        assert invitation.status == "PENDING"  # detached pre-accept snapshot


async def test_invitation_is_email_bound_and_single_use(session_factory, monkeypatch) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        _, raw = await create_invitation(
            session, actor_user_id=admin.id, email="invitee@example.com"
        )
    async with session_factory() as session:
        with pytest.raises(HTTPException) as mismatch:
            await accept_invitation(session, _invite_payload("attacker@example.com", raw))
        assert mismatch.value.status_code == 403
        await session.rollback()
    async with session_factory() as session:
        created = await accept_invitation(session, _invite_payload("invitee@example.com", raw))
        assert created.email == "invitee@example.com"
    async with session_factory() as session:
        with pytest.raises(HTTPException) as replay:
            await accept_invitation(session, _invite_payload("invitee@example.com", raw))
        assert replay.value.status_code == 400


async def test_expired_and_cancelled_invitations_cannot_create_accounts(
    session_factory, monkeypatch
) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        expired, expired_raw = await create_invitation(
            session, actor_user_id=admin.id, email="expired@example.com"
        )
        expired.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(HTTPException) as rejected:
            await accept_invitation(
                session, _invite_payload("expired@example.com", expired_raw)
            )
        assert rejected.value.status_code == 400

    async with session_factory() as session:
        cancelled, cancelled_raw = await create_invitation(
            session, actor_user_id=admin.id, email="cancelled@example.com"
        )
        await cancel_invitation(
            session, cancelled.id, actor_user_id=admin.id
        )
    async with session_factory() as session:
        with pytest.raises(HTTPException) as rejected:
            await accept_invitation(
                session, _invite_payload("cancelled@example.com", cancelled_raw)
            )
        assert rejected.value.status_code == 400
    async with session_factory() as verify:
        assert await verify.scalar(select(text("count(*)")).select_from(User)) == 1


async def test_invitation_acceptance_is_atomic_under_concurrency(
    session_factory, monkeypatch
) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        _, raw = await create_invitation(
            session, actor_user_id=admin.id, email="concurrent@example.com"
        )

    async def attempt():
        async with session_factory() as session:
            try:
                user = await accept_invitation(
                    session, _invite_payload("concurrent@example.com", raw)
                )
                return ("created", user.id)
            except HTTPException as exc:
                await session.rollback()
                return ("rejected", exc.status_code)

    results = await asyncio.gather(attempt(), attempt())
    assert sorted(item[0] for item in results) == ["created", "rejected"]
    async with session_factory() as verify:
        assert await verify.scalar(select(text("count(*)")).select_from(User)) == 2
        assert await verify.scalar(select(text("count(*)")).select_from(Household)) == 2


async def test_password_reset_is_one_time_and_revokes_existing_sessions(
    session_factory, monkeypatch
) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        _, refresh = await issue_session(session, admin)
        assert refresh
    async with session_factory() as session:
        raw, _ = await issue_manual_password_reset(
            session, actor_user_id=admin.id, target_user_id=admin.id
        )
    async with session_factory() as session:
        await complete_password_reset(
            session, token=raw, new_password="senha-nova-forte-testes"
        )
    async with session_factory() as verify:
        active_sessions = await verify.scalar(
            select(text("count(*)")).select_from(AuthSession).where(AuthSession.revoked_at.is_(None))
        )
        assert active_sessions == 0
    async with session_factory() as session:
        with pytest.raises(HTTPException) as replay:
            await complete_password_reset(
                session, token=raw, new_password="outra-senha-forte-testes"
            )
        assert replay.value.status_code == 400


async def test_concurrent_manual_password_resets_leave_only_one_active_token(
    session_factory, monkeypatch
) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)

    first_at_commit = asyncio.Event()
    release_first = asyncio.Event()
    second_was_serialized = False

    async with session_factory() as first, session_factory() as second:
        original_first_commit = first.commit

        async def hold_first_commit() -> None:
            first_at_commit.set()
            await release_first.wait()
            await original_first_commit()

        first.commit = hold_first_commit  # type: ignore[method-assign]
        first_task = asyncio.create_task(
            issue_manual_password_reset(
                first,
                actor_user_id=admin.id,
                target_user_id=admin.id,
            )
        )
        await asyncio.wait_for(first_at_commit.wait(), timeout=2)

        second_task = asyncio.create_task(
            issue_manual_password_reset(
                second,
                actor_user_id=admin.id,
                target_user_id=admin.id,
            )
        )
        try:
            await asyncio.wait_for(asyncio.shield(second_task), timeout=0.25)
        except TimeoutError:
            second_was_serialized = True
        finally:
            release_first.set()
            await asyncio.gather(first_task, second_task)

    assert second_was_serialized is True

    async with session_factory() as verify:
        active_tokens = await verify.scalar(
            select(text("count(*)"))
            .select_from(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == admin.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
        )
        assert active_tokens == 1


async def test_expired_password_reset_token_is_rejected(
    session_factory, monkeypatch
) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        raw, _ = await issue_manual_password_reset(
            session, actor_user_id=admin.id, target_user_id=admin.id
        )
        token = await session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_one_time_token(raw)
            )
        )
        assert token is not None
        token.expires_at = utcnow() - timedelta(seconds=1)
        await session.commit()
    async with session_factory() as session:
        with pytest.raises(HTTPException) as rejected:
            await complete_password_reset(
                session, token=raw, new_password="senha-nova-forte-testes"
            )
        assert rejected.value.status_code == 400


async def test_last_platform_admin_cannot_be_deactivated(session_factory, monkeypatch) -> None:
    admin = await _bootstrap(session_factory, monkeypatch)
    async with session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await set_user_active(
                session,
                actor_user_id=admin.id,
                target_user_id=admin.id,
                active=False,
            )
        assert blocked.value.status_code == 409
        await session.rollback()
    async with session_factory() as verify:
        user = await verify.get(User, admin.id)
        assert user is not None and user.is_active is True
