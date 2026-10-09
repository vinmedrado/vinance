from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.auth.models import User
from backend.app.financial_state import service
from backend.app.financial_state.models import Household, HouseholdInvitation, HouseholdMember
from backend.app.financial_state.schemas import (
    HouseholdCreate,
    HouseholdInvitationCreate,
    HouseholdMemberUpdate,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


def _assert_isolated_database() -> None:
    assert TEST_DATABASE_URL is not None
    database_name = (make_url(TEST_DATABASE_URL).database or "").lower()
    assert "test" in database_name, "Phase B PostgreSQL tests require an isolated test database"


async def _user(session: AsyncSession, label: str) -> tuple[User, Household, HouseholdMember]:
    user = User(
        email=f"{label}-{uuid4()}@example.com".lower(),
        full_name=label,
        hashed_password="not-used",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    personal = Household(
        name=f"{label} — pessoal",
        household_type="PERSONAL",
        created_by_user_id=user.id,
        status="ACTIVE",
    )
    session.add(personal)
    await session.flush()
    membership = HouseholdMember(
        household_id=personal.id,
        user_id=user.id,
        role="OWNER",
        status="ACTIVE",
        is_default=True,
    )
    session.add(membership)
    await session.commit()
    return user, personal, membership


@pytest.mark.asyncio
async def test_invitation_requires_consent_and_reactivation_requires_new_acceptance() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            owner, _, _ = await _user(session, "Owner")
            invitee, invitee_personal, _ = await _user(session, "Invitee")
            outsider, _, _ = await _user(session, "Outsider")
            shared = await service.create_household(
                session, user_id=owner.id, payload=HouseholdCreate(name="Casa consentida")
            )

            invitation = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=invitee.email.upper()),
            )
            assert invitation["status"] == "PENDING"
            assert invitation["invited_email_normalized"] == invitee.email
            with pytest.raises(service.HouseholdNotFoundError):
                await service.get_household_access(session, household_id=shared.id, user_id=invitee.id)
            with pytest.raises(service.HouseholdConflictError):
                await service.create_invitation(
                    session,
                    household_id=shared.id,
                    user_id=owner.id,
                    payload=HouseholdInvitationCreate(email=invitee.email),
                )
            expired = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(
                    email=outsider.email,
                    expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                ),
            )
            replacement = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=outsider.email),
            )
            assert replacement["id"] != expired["id"]
            with pytest.raises(service.FinancialResourceNotFoundError):
                await service.accept_invitation(
                    session, invitation_id=invitation["id"], user_id=outsider.id
                )

            accepted = await service.accept_invitation(
                session, invitation_id=invitation["id"], user_id=invitee.id
            )
            assert accepted["status"] == "ACCEPTED"
            repeated = await service.accept_invitation(
                session, invitation_id=invitation["id"], user_id=invitee.id
            )
            assert repeated["id"] == accepted["id"]
            _, joined = await service.get_household_access(
                session, household_id=shared.id, user_id=invitee.id
            )
            assert joined.role == "MEMBER"
            assert joined.is_default is False
            assert (await service.get_default_household(session, user_id=invitee.id)).id == invitee_personal.id

            await service.remove_member(
                session,
                household_id=shared.id,
                member_id=joined.id,
                user_id=owner.id,
            )
            assert (await service.get_default_household(session, user_id=invitee.id)).id == invitee_personal.id
            with pytest.raises(service.HouseholdNotFoundError):
                await service.get_household_access(session, household_id=shared.id, user_id=invitee.id)
            reinvite = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=invitee.email),
            )
            await service.accept_invitation(
                session, invitation_id=reinvite["id"], user_id=invitee.id
            )
            _, rejoined = await service.get_household_access(
                session, household_id=shared.id, user_id=invitee.id
            )
            assert rejoined.id == joined.id
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_decline_cancel_default_leave_and_sole_owner_rules() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            owner, owner_personal, _ = await _user(session, "Owner-rules")
            member, member_personal, _ = await _user(session, "Member-rules")
            shared = await service.create_household(
                session, user_id=owner.id, payload=HouseholdCreate(name="Casa rules")
            )
            first = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=member.email),
            )
            declined = await service.decline_invitation(
                session, invitation_id=first["id"], user_id=member.id
            )
            assert declined["status"] == "DECLINED"
            with pytest.raises(service.HouseholdNotFoundError):
                await service.get_household_access(session, household_id=shared.id, user_id=member.id)

            second = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=member.email),
            )
            cancelled = await service.cancel_invitation(
                session,
                household_id=shared.id,
                invitation_id=second["id"],
                user_id=owner.id,
            )
            assert cancelled["status"] == "CANCELLED"
            with pytest.raises(service.HouseholdConflictError):
                await service.accept_invitation(
                    session, invitation_id=second["id"], user_id=member.id
                )

            third = await service.create_invitation(
                session,
                household_id=shared.id,
                user_id=owner.id,
                payload=HouseholdInvitationCreate(email=member.email),
            )
            await service.accept_invitation(
                session, invitation_id=third["id"], user_id=member.id
            )
            await service.set_default_household(
                session, household_id=shared.id, user_id=member.id
            )
            assert (await service.get_default_household(session, user_id=member.id)).id == shared.id
            await service.leave_household(session, household_id=shared.id, user_id=member.id)
            assert (await service.get_default_household(session, user_id=member.id)).id == member_personal.id

            with pytest.raises(service.HouseholdConflictError):
                await service.leave_household(session, household_id=shared.id, user_id=owner.id)
            owner_membership = (await service.get_household_access(
                session, household_id=shared.id, user_id=owner.id
            ))[1]
            with pytest.raises(service.HouseholdConflictError):
                await service.update_member(
                    session,
                    household_id=shared.id,
                    member_id=owner_membership.id,
                    user_id=owner.id,
                    payload=HouseholdMemberUpdate(role="MEMBER"),
                )
            assert (await service.get_default_household(session, user_id=owner.id)).id == owner_personal.id
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_accept_creates_one_logical_membership() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup:
        owner, _, _ = await _user(setup, "Concurrent-owner")
        invitee, _, _ = await _user(setup, "Concurrent-invitee")
        shared = await service.create_household(
            setup, user_id=owner.id, payload=HouseholdCreate(name="Casa concurrent")
        )
        invitation = await service.create_invitation(
            setup,
            household_id=shared.id,
            user_id=owner.id,
            payload=HouseholdInvitationCreate(email=invitee.email),
        )

    async def accept_once() -> dict:
        async with factory() as concurrent_session:
            return await service.accept_invitation(
                concurrent_session,
                invitation_id=invitation["id"],
                user_id=invitee.id,
            )

    first, second = await asyncio.gather(accept_once(), accept_once())
    assert first["id"] == second["id"]
    async with factory() as verify:
        membership_count = await verify.scalar(
            select(func.count(HouseholdMember.id)).where(
                HouseholdMember.household_id == shared.id,
                HouseholdMember.user_id == invitee.id,
                HouseholdMember.status == "ACTIVE",
            )
        )
        accepted_count = await verify.scalar(
            select(func.count(HouseholdInvitation.id)).where(
                HouseholdInvitation.id == invitation["id"],
                HouseholdInvitation.status == "ACCEPTED",
            )
        )
        assert membership_count == 1
        assert accepted_count == 1
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["accept", "decline"])
async def test_cancelled_invitation_wins_over_stale_invitee_session(decision: str) -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup:
        owner, _, _ = await _user(setup, f"Cancel-owner-{decision}")
        invitee, _, _ = await _user(setup, f"Cancel-invitee-{decision}")
        shared = await service.create_household(
            setup, user_id=owner.id, payload=HouseholdCreate(name=f"Casa cancel {decision}")
        )
        invitation = await service.create_invitation(
            setup,
            household_id=shared.id,
            user_id=owner.id,
            payload=HouseholdInvitationCreate(email=invitee.email),
        )

    async with factory() as stale_invitee_session:
        loaded = await stale_invitee_session.get(HouseholdInvitation, invitation["id"])
        assert loaded is not None and loaded.status == "PENDING"

        async with factory() as owner_session:
            cancelled = await service.cancel_invitation(
                owner_session,
                household_id=shared.id,
                invitation_id=invitation["id"],
                user_id=owner.id,
            )
            assert cancelled["status"] == "CANCELLED"

        decide = (
            service.accept_invitation
            if decision == "accept"
            else service.decline_invitation
        )
        with pytest.raises(service.HouseholdConflictError):
            await decide(
                stale_invitee_session,
                invitation_id=invitation["id"],
                user_id=invitee.id,
            )

    async with factory() as verify:
        persisted = await verify.get(HouseholdInvitation, invitation["id"])
        membership_count = await verify.scalar(
            select(func.count(HouseholdMember.id)).where(
                HouseholdMember.household_id == shared.id,
                HouseholdMember.user_id == invitee.id,
                HouseholdMember.status == "ACTIVE",
            )
        )
        assert persisted is not None and persisted.status == "CANCELLED"
        assert membership_count == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_owner_changes_preserve_at_least_one_owner() -> None:
    assert TEST_DATABASE_URL is not None
    _assert_isolated_database()
    engine = create_async_engine(TEST_DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup:
        owner_a, _, _ = await _user(setup, "Owner-a")
        owner_b, _, _ = await _user(setup, "Owner-b")
        shared = await service.create_household(
            setup, user_id=owner_a.id, payload=HouseholdCreate(name="Casa owners")
        )
        invitation = await service.create_invitation(
            setup,
            household_id=shared.id,
            user_id=owner_a.id,
            payload=HouseholdInvitationCreate(email=owner_b.email, role="OWNER"),
        )
        await service.accept_invitation(
            setup, invitation_id=invitation["id"], user_id=owner_b.id
        )
        rows = await setup.execute(
            select(HouseholdMember).where(
                HouseholdMember.household_id == shared.id,
                HouseholdMember.status == "ACTIVE",
            )
        )
        memberships = {row.user_id: row.id for row in rows.scalars().all()}

    async def demote(actor_id: int, target_id: int) -> object:
        async with factory() as concurrent_session:
            try:
                return await service.update_member(
                    concurrent_session,
                    household_id=shared.id,
                    member_id=memberships[target_id],
                    user_id=actor_id,
                    payload=HouseholdMemberUpdate(role="MEMBER"),
                )
            except Exception as exc:  # outcome is asserted below
                return exc

    results = await asyncio.gather(
        demote(owner_a.id, owner_b.id),
        demote(owner_b.id, owner_a.id),
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert any(isinstance(result, service.FinancialStateDomainError) for result in results)
    async with factory() as verify:
        owner_count = await verify.scalar(
            select(func.count(HouseholdMember.id)).where(
                HouseholdMember.household_id == shared.id,
                HouseholdMember.status == "ACTIVE",
                HouseholdMember.role == "OWNER",
            )
        )
        assert owner_count == 1
    await engine.dispose()
