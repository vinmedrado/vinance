from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TypeVar

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import User
from backend.app.auth.normalization import normalize_email
from backend.app.catalog.models import AssetCatalog
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial_state.engine import calculate_financial_state
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    Household,
    HouseholdInvitation,
    HouseholdMember,
    OwnedAsset,
)


logger = logging.getLogger(__name__)


class FinancialStateDomainError(Exception):
    pass


class HouseholdNotFoundError(FinancialStateDomainError):
    pass


class HouseholdPermissionError(FinancialStateDomainError):
    pass


class HouseholdConflictError(FinancialStateDomainError):
    pass


class FinancialResourceNotFoundError(FinancialStateDomainError):
    pass


class FinancialStateValidationError(FinancialStateDomainError):
    pass


ResourceModel = TypeVar("ResourceModel", Income, Expense, FinancialLiability, OwnedAsset, FinancialGoal)

PRIVACY_CONTRACT_VERSION = "household-privacy-v1"
PERSONAL_DECISION_SCOPE = "PERSONAL"
SHARED_DECISION_SCOPE = "HOUSEHOLD_SHARED"

_RESOURCE_CHANGE_CATEGORY: dict[type[Any], str] = {
    Income: "FINANCIAL_DATA",
    Expense: "FINANCIAL_DATA",
    FinancialLiability: "DEBT",
    OwnedAsset: "ASSETS",
    FinancialGoal: "GOALS",
}


async def _mark_continuous_dirty(
    session: AsyncSession, *, household_id: int, category: str
) -> None:
    # Local import prevents a module cycle: A6 consumes this canonical service.
    from backend.app.continuous_autopilot.service import mark_household_dirty

    await mark_household_dirty(
        session,
        household_id=household_id,
        category=category,
    )


async def _mark_resource_dirty_if_shared_visible(
    session: AsyncSession,
    *,
    household: Household,
    category: str,
    ownership_scopes: set[str],
) -> None:
    """Do not expose private activity through a shared reevaluation marker."""

    if household.household_type == "PERSONAL" or "HOUSEHOLD" in ownership_scopes:
        await _mark_continuous_dirty(
            session,
            household_id=household.id,
            category=category,
        )


async def get_household_access(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> tuple[Household, HouseholdMember]:
    result = await session.execute(
        select(Household, HouseholdMember)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(
            Household.id == household_id,
            Household.status == "ACTIVE",
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
        )
    )
    access = result.first()
    if access is None:
        raise HouseholdNotFoundError("household not found")
    return access[0], access[1]


async def require_household_owner(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> tuple[Household, HouseholdMember]:
    household, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    if membership.role != "OWNER":
        raise HouseholdPermissionError("household owner permission required")
    return household, membership


async def get_default_household(
    session: AsyncSession,
    *,
    user_id: int,
) -> Household:
    result = await session.execute(
        select(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(
            Household.status == "ACTIVE",
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
        )
        .order_by(
            HouseholdMember.is_default.desc(),
            (Household.household_type == "PERSONAL").desc(),
            Household.id.asc(),
        )
        .limit(1)
    )
    household = result.scalar_one_or_none()
    if household is None:
        raise HouseholdNotFoundError("default household not found")
    return household


async def list_households(session: AsyncSession, *, user_id: int) -> list[Household]:
    result = await session.execute(
        select(Household)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(
            Household.status == "ACTIVE",
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
        )
        .order_by(HouseholdMember.is_default.desc(), Household.id.asc())
    )
    return list(result.scalars().all())


async def create_household(
    session: AsyncSession,
    *,
    user_id: int,
    payload: Any,
) -> Household:
    values = payload.model_dump()
    if values.get("household_type") != "SHARED":
        raise FinancialStateValidationError("new households must be SHARED")
    household = Household(
        name=values["name"],
        household_type="SHARED",
        created_by_user_id=user_id,
        status="ACTIVE",
    )
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMember(
            household_id=household.id,
            user_id=user_id,
            role="OWNER",
            status="ACTIVE",
            is_default=False,
        )
    )
    await _mark_continuous_dirty(
        session, household_id=household.id, category="HOUSEHOLD"
    )
    await session.commit()
    await session.refresh(household)
    return household


async def update_household(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    payload: Any,
) -> Household:
    await _lock_household(session, household_id=household_id)
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "ARCHIVED" and household.household_type == "PERSONAL":
        raise HouseholdConflictError("personal household cannot be archived")
    for field, value in values.items():
        if value is not None:
            setattr(household, field, value)
    await _mark_continuous_dirty(
        session, household_id=household_id, category="HOUSEHOLD"
    )
    await session.commit()
    await session.refresh(household)
    return household


async def _member_read(
    session: AsyncSession,
    membership: HouseholdMember,
) -> dict[str, Any]:
    user = await session.get(User, membership.user_id)
    return {
        "id": membership.id,
        "household_id": membership.household_id,
        "user_id": membership.user_id,
        "role": membership.role,
        "status": membership.status,
        "is_default": membership.is_default,
        "joined_at": membership.joined_at,
        "updated_at": membership.updated_at,
        "email": user.email if user else None,
        "full_name": user.full_name if user else None,
    }


async def list_members(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> list[dict[str, Any]]:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    result = await session.execute(
        select(HouseholdMember, User)
        .join(User, User.id == HouseholdMember.user_id)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
        )
        .order_by(HouseholdMember.id.asc())
    )
    return [
        {
            "id": member.id,
            "household_id": member.household_id,
            "user_id": member.user_id,
            "role": member.role,
            "status": member.status,
            "is_default": member.is_default,
            "joined_at": member.joined_at,
            "updated_at": member.updated_at,
            "email": member_user.email,
            "full_name": member_user.full_name,
        }
        for member, member_user in result.all()
    ]


async def _clear_user_default(
    session: AsyncSession,
    *,
    user_id: int,
    except_membership_id: int | None = None,
) -> None:
    statement = update(HouseholdMember).where(
        HouseholdMember.user_id == user_id,
        HouseholdMember.status == "ACTIVE",
        HouseholdMember.is_default.is_(True),
    )
    if except_membership_id is not None:
        statement = statement.where(HouseholdMember.id != except_membership_id)
    await session.execute(statement.values(is_default=False))


async def _restore_personal_default(session: AsyncSession, *, user_id: int) -> None:
    result = await session.execute(
        select(HouseholdMember)
        .join(Household, Household.id == HouseholdMember.household_id)
        .where(
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
            Household.household_type == "PERSONAL",
            Household.status == "ACTIVE",
        )
        .limit(1)
    )
    personal = result.scalar_one_or_none()
    if personal is not None:
        await _clear_user_default(
            session, user_id=user_id, except_membership_id=personal.id
        )
        personal.is_default = True


async def _active_owner_count(
    session: AsyncSession,
    *,
    household_id: int,
    excluding_member_id: int,
) -> int:
    result = await session.execute(
        select(func.count(HouseholdMember.id)).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
            HouseholdMember.role == "OWNER",
            HouseholdMember.id != excluding_member_id,
        )
    )
    return int(result.scalar_one())


async def _lock_household(session: AsyncSession, *, household_id: int) -> None:
    """Serialize membership administration for one household, never globally."""

    await session.execute(
        select(Household.id)
        .where(Household.id == household_id)
        .with_for_update()
    )


async def update_member(
    session: AsyncSession,
    *,
    household_id: int,
    member_id: int,
    user_id: int,
    payload: Any,
) -> dict[str, Any]:
    await _lock_household(session, household_id=household_id)
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    if household.household_type != "SHARED":
        raise HouseholdConflictError("personal household membership cannot be administered")
    result = await session.execute(
        select(HouseholdMember)
        .where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
        )
        .with_for_update()
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise FinancialResourceNotFoundError("member not found")
    values = payload.model_dump(exclude_unset=True)
    if set(values) - {"role"}:
        raise FinancialStateValidationError("only role can be changed by household administration")
    removes_owner = membership.role == "OWNER" and values.get("role") == "MEMBER"
    if removes_owner and await _active_owner_count(
        session,
        household_id=household_id,
        excluding_member_id=membership.id,
    ) == 0:
        raise HouseholdConflictError("household must retain an active owner")
    for field, value in values.items():
        if value is not None:
            setattr(membership, field, value)
    await _mark_continuous_dirty(
        session, household_id=household_id, category="HOUSEHOLD"
    )
    await session.commit()
    await session.refresh(membership)
    return await _member_read(session, membership)


async def remove_member(
    session: AsyncSession,
    *,
    household_id: int,
    member_id: int,
    user_id: int,
) -> None:
    await _lock_household(session, household_id=household_id)
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    if household.household_type != "SHARED":
        raise HouseholdConflictError("personal household member cannot be removed")
    result = await session.execute(
        select(HouseholdMember)
        .where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise FinancialResourceNotFoundError("member not found")
    if membership.user_id == user_id:
        raise HouseholdConflictError("use the leave endpoint to leave a household")
    await session.execute(
        select(User.id).where(User.id == membership.user_id).with_for_update()
    )
    locked_result = await session.execute(
        select(HouseholdMember)
        .where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == "ACTIVE",
        )
        .with_for_update()
    )
    membership = locked_result.scalar_one_or_none()
    if membership is None:
        raise FinancialResourceNotFoundError("member not found")
    if membership.role == "OWNER" and await _active_owner_count(
        session,
        household_id=household_id,
        excluding_member_id=membership.id,
    ) == 0:
        raise HouseholdConflictError("household must retain an active owner")
    was_default = bool(membership.is_default)
    membership.status = "REMOVED"
    membership.is_default = False
    if was_default:
        await _restore_personal_default(session, user_id=membership.user_id)
    await _mark_continuous_dirty(
        session, household_id=household_id, category="HOUSEHOLD"
    )
    await session.commit()
    logger.info(
        "household_member_removed household_id=%s member_id=%s actor_user_id=%s",
        household_id,
        member_id,
        user_id,
    )


async def _invitation_read(
    session: AsyncSession,
    invitation: HouseholdInvitation,
) -> dict[str, Any]:
    household = await session.get(Household, invitation.household_id)
    inviter = await session.get(User, invitation.invited_by_user_id)
    status = invitation.status
    now = datetime.now(timezone.utc)
    if status == "PENDING" and invitation.expires_at is not None and invitation.expires_at <= now:
        status = "EXPIRED"
    return {
        "id": invitation.id,
        "household_id": invitation.household_id,
        "household_name": household.name if household else "Household",
        "invited_email_normalized": invitation.invited_email_normalized,
        "invited_user_id": invitation.invited_user_id,
        "invited_by_user_id": invitation.invited_by_user_id,
        "invited_by_name": inviter.full_name if inviter else None,
        "role": invitation.role,
        "status": status,
        "expires_at": invitation.expires_at,
        "accepted_at": invitation.accepted_at,
        "declined_at": invitation.declined_at,
        "cancelled_at": invitation.cancelled_at,
        "created_at": invitation.created_at,
        "updated_at": invitation.updated_at,
    }


async def create_invitation(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    payload: Any,
) -> dict[str, Any]:
    await _lock_household(session, household_id=household_id)
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    if household.household_type != "SHARED":
        raise HouseholdConflictError("personal household cannot accept invitations")
    inviter = await session.get(User, user_id)
    if inviter is None:
        raise FinancialResourceNotFoundError("user not found")
    email = normalize_email(str(payload.email))
    if email == normalize_email(inviter.email):
        raise HouseholdConflictError("you are already a household member")
    invited_result = await session.execute(
        select(User).where(User.email == email, User.is_active.is_(True))
    )
    invited_user = invited_result.scalar_one_or_none()
    if invited_user is not None:
        membership_result = await session.execute(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == invited_user.id,
                HouseholdMember.status == "ACTIVE",
            )
        )
        if membership_result.scalar_one_or_none() is not None:
            raise HouseholdConflictError("user is already a household member")
    await session.execute(
        update(HouseholdInvitation)
        .where(
            HouseholdInvitation.household_id == household_id,
            HouseholdInvitation.invited_email_normalized == email,
            HouseholdInvitation.status == "PENDING",
            HouseholdInvitation.expires_at.is_not(None),
            HouseholdInvitation.expires_at <= datetime.now(timezone.utc),
        )
        .values(status="EXPIRED", updated_at=func.now())
    )
    existing_result = await session.execute(
        select(HouseholdInvitation).where(
            HouseholdInvitation.household_id == household_id,
            HouseholdInvitation.invited_email_normalized == email,
            HouseholdInvitation.status == "PENDING",
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HouseholdConflictError("a pending invitation already exists")
    invitation = HouseholdInvitation(
        household_id=household_id,
        invited_email_normalized=email,
        invited_user_id=invited_user.id if invited_user else None,
        invited_by_user_id=user_id,
        role=payload.role,
        status="PENDING",
        expires_at=payload.expires_at,
    )
    session.add(invitation)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HouseholdConflictError("a pending invitation already exists") from exc
    await session.refresh(invitation)
    logger.info(
        "household_invitation_created household_id=%s invitation_id=%s actor_user_id=%s",
        household_id,
        invitation.id,
        user_id,
    )
    return await _invitation_read(session, invitation)


async def list_household_invitations(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> list[dict[str, Any]]:
    await require_household_owner(session, household_id=household_id, user_id=user_id)
    result = await session.execute(
        select(HouseholdInvitation)
        .where(HouseholdInvitation.household_id == household_id)
        .order_by(HouseholdInvitation.created_at.desc(), HouseholdInvitation.id.desc())
    )
    return [await _invitation_read(session, item) for item in result.scalars().all()]


async def list_incoming_invitations(
    session: AsyncSession,
    *,
    user_id: int,
) -> list[dict[str, Any]]:
    user = await session.get(User, user_id)
    if user is None:
        raise FinancialResourceNotFoundError("user not found")
    email = normalize_email(user.email)
    result = await session.execute(
        select(HouseholdInvitation)
        .where(
            or_(
                HouseholdInvitation.invited_user_id == user_id,
                HouseholdInvitation.invited_email_normalized == email,
            )
        )
        .order_by(HouseholdInvitation.created_at.desc(), HouseholdInvitation.id.desc())
    )
    return [await _invitation_read(session, item) for item in result.scalars().all()]


async def _locked_invitation_for_invitee(
    session: AsyncSession,
    *,
    invitation_id: int,
    user_id: int,
) -> tuple[HouseholdInvitation, User]:
    user = await session.get(User, user_id)
    if user is None:
        raise FinancialResourceNotFoundError("invitation not found")
    initial_result = await session.execute(
        select(HouseholdInvitation).where(HouseholdInvitation.id == invitation_id)
    )
    invitation = initial_result.scalar_one_or_none()
    if invitation is None or (
        invitation.invited_user_id not in (None, user_id)
        or invitation.invited_email_normalized != normalize_email(user.email)
    ):
        raise FinancialResourceNotFoundError("invitation not found")
    await _lock_household(session, household_id=invitation.household_id)
    result = await session.execute(
        select(HouseholdInvitation)
        .where(HouseholdInvitation.id == invitation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    invitation = result.scalar_one_or_none()
    if invitation is None or (
        invitation.invited_user_id not in (None, user_id)
        or invitation.invited_email_normalized != normalize_email(user.email)
    ):
        raise FinancialResourceNotFoundError("invitation not found")
    return invitation, user


async def accept_invitation(
    session: AsyncSession,
    *,
    invitation_id: int,
    user_id: int,
) -> dict[str, Any]:
    invitation, user = await _locked_invitation_for_invitee(
        session, invitation_id=invitation_id, user_id=user_id
    )
    membership_result = await session.execute(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == invitation.household_id,
            HouseholdMember.user_id == user_id,
        )
        .with_for_update()
    )
    membership = membership_result.scalar_one_or_none()
    if invitation.status == "ACCEPTED":
        if membership is None or membership.status != "ACTIVE":
            raise HouseholdConflictError("accepted invitation has no active membership")
        return await _invitation_read(session, invitation)
    if invitation.status != "PENDING":
        raise HouseholdConflictError("invitation is no longer pending")
    now = datetime.now(timezone.utc)
    if invitation.expires_at is not None and invitation.expires_at <= now:
        invitation.status = "EXPIRED"
        await session.commit()
        raise HouseholdConflictError("invitation has expired")
    household = await session.get(Household, invitation.household_id)
    if household is None or household.status != "ACTIVE" or household.household_type != "SHARED":
        raise FinancialResourceNotFoundError("invitation not found")
    if membership is None:
        membership = HouseholdMember(
            household_id=invitation.household_id,
            user_id=user_id,
            role=invitation.role,
            status="ACTIVE",
            is_default=False,
        )
        session.add(membership)
    elif membership.status == "REMOVED":
        membership.role = invitation.role
        membership.status = "ACTIVE"
        membership.is_default = False
    invitation.invited_user_id = user.id
    invitation.status = "ACCEPTED"
    invitation.accepted_at = now
    await _mark_continuous_dirty(
        session, household_id=invitation.household_id, category="HOUSEHOLD"
    )
    await session.commit()
    await session.refresh(invitation)
    logger.info(
        "household_invitation_accepted household_id=%s invitation_id=%s actor_user_id=%s",
        invitation.household_id,
        invitation.id,
        user_id,
    )
    return await _invitation_read(session, invitation)


async def decline_invitation(
    session: AsyncSession,
    *,
    invitation_id: int,
    user_id: int,
) -> dict[str, Any]:
    invitation, _ = await _locked_invitation_for_invitee(
        session, invitation_id=invitation_id, user_id=user_id
    )
    if invitation.status == "DECLINED":
        return await _invitation_read(session, invitation)
    if invitation.status != "PENDING":
        raise HouseholdConflictError("invitation is no longer pending")
    invitation.status = "DECLINED"
    invitation.declined_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(invitation)
    logger.info(
        "household_invitation_declined household_id=%s invitation_id=%s actor_user_id=%s",
        invitation.household_id,
        invitation.id,
        user_id,
    )
    return await _invitation_read(session, invitation)


async def cancel_invitation(
    session: AsyncSession,
    *,
    household_id: int,
    invitation_id: int,
    user_id: int,
) -> dict[str, Any]:
    await _lock_household(session, household_id=household_id)
    await require_household_owner(session, household_id=household_id, user_id=user_id)
    result = await session.execute(
        select(HouseholdInvitation)
        .where(
            HouseholdInvitation.id == invitation_id,
            HouseholdInvitation.household_id == household_id,
        )
        .with_for_update()
    )
    invitation = result.scalar_one_or_none()
    if invitation is None:
        raise FinancialResourceNotFoundError("invitation not found")
    if invitation.status == "CANCELLED":
        return await _invitation_read(session, invitation)
    if invitation.status != "PENDING":
        raise HouseholdConflictError("invitation is no longer pending")
    invitation.status = "CANCELLED"
    invitation.cancelled_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(invitation)
    logger.info(
        "household_invitation_cancelled household_id=%s invitation_id=%s actor_user_id=%s",
        household_id,
        invitation.id,
        user_id,
    )
    return await _invitation_read(session, invitation)


async def set_default_household(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> Household:
    await _lock_household(session, household_id=household_id)
    household, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    locked_result = await session.execute(
        select(HouseholdMember)
        .where(HouseholdMember.id == membership.id)
        .with_for_update()
    )
    membership = locked_result.scalar_one()
    await _clear_user_default(
        session, user_id=user_id, except_membership_id=membership.id
    )
    membership.is_default = True
    await session.commit()
    return household


async def leave_household(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> None:
    await _lock_household(session, household_id=household_id)
    household, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    if household.household_type != "SHARED":
        raise HouseholdConflictError("personal household cannot be left")
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    locked_result = await session.execute(
        select(HouseholdMember)
        .where(HouseholdMember.id == membership.id)
        .with_for_update()
    )
    membership = locked_result.scalar_one()
    if membership.role == "OWNER" and await _active_owner_count(
        session,
        household_id=household_id,
        excluding_member_id=membership.id,
    ) == 0:
        raise HouseholdConflictError("transfer ownership before leaving the household")
    was_default = bool(membership.is_default)
    membership.status = "REMOVED"
    membership.is_default = False
    if was_default:
        await _restore_personal_default(session, user_id=user_id)
    await _mark_continuous_dirty(
        session, household_id=household_id, category="HOUSEHOLD"
    )
    await session.commit()
    logger.info(
        "household_member_left household_id=%s member_id=%s actor_user_id=%s",
        household_id,
        membership.id,
        user_id,
    )


def _visible_resource_clause(model: type[ResourceModel], *, user_id: int) -> Any:
    """PERSONAL is owner-only; HOUSEHOLD is visible to active members."""

    return or_(
        model.ownership_scope == "HOUSEHOLD",
        and_(
            model.ownership_scope == "PERSONAL",
            model.user_id == user_id,
        ),
    )


async def _get_visible_record(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    record_id: int,
    user_id: int,
) -> ResourceModel:
    result = await session.execute(
        select(model).where(
            model.id == record_id,
            model.household_id == household_id,
            _visible_resource_clause(model, user_id=user_id),
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        # A private record owned by another member is indistinguishable from
        # a missing or cross-household resource.
        raise FinancialResourceNotFoundError("financial resource not found")
    return record


def _can_mutate_record(record: Any, membership: HouseholdMember, user_id: int) -> bool:
    if record.ownership_scope == "PERSONAL":
        return record.user_id == user_id
    return record.user_id == user_id or membership.role == "OWNER"


async def _validate_catalog_reference(
    session: AsyncSession,
    *,
    asset_catalog_id: int | None,
) -> None:
    if asset_catalog_id is not None and await session.get(AssetCatalog, asset_catalog_id) is None:
        raise FinancialStateValidationError("asset_catalog_id not found")


async def create_resource(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    user_id: int,
    payload: Any,
) -> ResourceModel:
    household, _ = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    values = payload.model_dump()
    if model is OwnedAsset:
        await _validate_catalog_reference(
            session, asset_catalog_id=values.get("asset_catalog_id")
        )
    record = model(household_id=household_id, user_id=user_id, **values)
    session.add(record)
    await _mark_resource_dirty_if_shared_visible(
        session,
        household=household,
        category=_RESOURCE_CHANGE_CATEGORY[model],
        ownership_scopes={str(values["ownership_scope"])},
    )
    await session.commit()
    await session.refresh(record)
    return record


async def list_resources(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    user_id: int,
) -> list[ResourceModel]:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    result = await session.execute(
        select(model)
        .where(
            model.household_id == household_id,
            _visible_resource_clause(model, user_id=user_id),
        )
        .order_by(model.id.desc())
    )
    return list(result.scalars().all())


async def get_resource(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    record_id: int,
    user_id: int,
) -> ResourceModel:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    return await _get_visible_record(
        session,
        model,
        household_id=household_id,
        record_id=record_id,
        user_id=user_id,
    )


async def update_resource(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    record_id: int,
    user_id: int,
    payload: Any,
) -> ResourceModel:
    household, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    record = await _get_visible_record(
        session,
        model,
        household_id=household_id,
        record_id=record_id,
        user_id=user_id,
    )
    if not _can_mutate_record(record, membership, user_id):
        raise HouseholdPermissionError("financial resource permission denied")
    values = payload.model_dump(exclude_unset=True)
    previous_scope = str(record.ownership_scope)
    if (
        previous_scope == "HOUSEHOLD"
        and values.get("ownership_scope") == "PERSONAL"
        and record.user_id != user_id
    ):
        # Administrators may maintain a shared record, but only its original
        # owner may withdraw it into that owner's private scope.
        raise HouseholdPermissionError("only the record owner can make it personal")
    for field, value in values.items():
        column = model.__table__.columns.get(field)
        if value is None and column is not None and not column.nullable:
            raise FinancialStateValidationError(f"{field} cannot be null")
    if "ownership_scope" in values and record.user_id != user_id:
        raise HouseholdPermissionError("only the record owner may change ownership scope")
    if model is OwnedAsset:
        await _validate_catalog_reference(
            session, asset_catalog_id=values.get("asset_catalog_id", record.asset_catalog_id)
        )
        final_name = values.get("name", record.name)
        final_catalog_id = values.get("asset_catalog_id", record.asset_catalog_id)
        if final_name is None and final_catalog_id is None:
            raise FinancialStateValidationError("name or asset_catalog_id is required")
    for field, value in values.items():
        setattr(record, field, value)
    await _mark_resource_dirty_if_shared_visible(
        session,
        household=household,
        category=_RESOURCE_CHANGE_CATEGORY[model],
        ownership_scopes={previous_scope, str(record.ownership_scope)},
    )
    await session.commit()
    await session.refresh(record)
    return record


async def delete_resource(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    record_id: int,
    user_id: int,
) -> None:
    household, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    record = await _get_visible_record(
        session,
        model,
        household_id=household_id,
        record_id=record_id,
        user_id=user_id,
    )
    if not _can_mutate_record(record, membership, user_id):
        raise HouseholdPermissionError("financial resource permission denied")
    await session.delete(record)
    await _mark_resource_dirty_if_shared_visible(
        session,
        household=household,
        category=_RESOURCE_CHANGE_CATEGORY[model],
        ownership_scopes={str(record.ownership_scope)},
    )
    await session.commit()


def _fields(record: Any, names: tuple[str, ...]) -> dict[str, Any]:
    return {name: getattr(record, name) for name in names}


async def build_normalized_inputs(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
) -> dict[str, Any]:
    household, _ = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    decision_scope = (
        SHARED_DECISION_SCOPE
        if household.household_type == "SHARED"
        else PERSONAL_DECISION_SCOPE
    )
    member_rows = await session.execute(
        select(HouseholdMember, User)
        .join(User, User.id == HouseholdMember.user_id)
        .where(HouseholdMember.household_id == household_id)
        .order_by(HouseholdMember.user_id.asc())
    )
    members = [
        {
            **_fields(
                member,
                ("id", "household_id", "user_id", "role", "status", "is_default"),
            ),
            "full_name": member_user.full_name,
        }
        for member, member_user in member_rows.all()
    ]
    async def load(model: Any) -> list[Any]:
        visibility = (
            model.ownership_scope == "HOUSEHOLD"
            if decision_scope == SHARED_DECISION_SCOPE
            else _visible_resource_clause(model, user_id=user_id)
        )
        result = await session.execute(
            select(model)
            .where(model.household_id == household_id, visibility)
            .order_by(model.id.asc())
        )
        return list(result.scalars().all())

    incomes = await load(Income)
    expenses = await load(Expense)
    liabilities = await load(FinancialLiability)
    assets = await load(OwnedAsset)
    goals = await load(FinancialGoal)
    profiles: list[FinancialProfile] = []
    if decision_scope == PERSONAL_DECISION_SCOPE:
        profile_result = await session.execute(
            select(FinancialProfile).where(FinancialProfile.user_id == user_id)
        )
        profiles = list(profile_result.scalars().all())
    return {
        "privacy_contract_version": PRIVACY_CONTRACT_VERSION,
        "decision_scope": decision_scope,
        "household": _fields(
            household,
            ("id", "name", "household_type", "created_by_user_id", "status"),
        ),
        "members": members,
        "incomes": [
            _fields(
                item,
                (
                    "id",
                    "household_id",
                    "user_id",
                    "ownership_scope",
                    "description",
                    "amount",
                    "income_type",
                    "received_at",
                    "is_recurring",
                    "updated_at",
                ),
            )
            for item in incomes
        ],
        "expenses": [
            _fields(
                item,
                (
                    "id",
                    "household_id",
                    "user_id",
                    "ownership_scope",
                    "description",
                    "amount",
                    "category",
                    "due_date",
                    "paid_at",
                    "is_paid",
                    "is_recurring",
                    "expense_nature",
                    "updated_at",
                ),
            )
            for item in expenses
        ],
        "liabilities": [
            _fields(
                item,
                (
                    "id",
                    "household_id",
                    "user_id",
                    "ownership_scope",
                    "name",
                    "liability_type",
                    "current_balance",
                    "monthly_payment",
                    "annual_interest_rate_pct",
                    "due_date",
                    "balance_as_of",
                    "currency",
                    "status",
                    "updated_at",
                ),
            )
            for item in liabilities
        ],
        "assets": [
            _fields(
                item,
                (
                    "id",
                    "household_id",
                    "user_id",
                    "ownership_scope",
                    "asset_class",
                    "asset_catalog_id",
                    "name",
                    "current_value",
                    "value_as_of",
                    "currency",
                    "status",
                    "updated_at",
                ),
            )
            for item in assets
        ],
        "goals": [
            _fields(
                item,
                (
                    "id",
                    "household_id",
                    "user_id",
                    "ownership_scope",
                    "name",
                    "target_amount",
                    "current_amount",
                    "deadline",
                    "priority",
                    "status",
                    "currency",
                    "updated_at",
                ),
            )
            for item in goals
        ],
        "financial_profiles": [
            _fields(
                item,
                (
                    "id",
                    "user_id",
                    "monthly_salary",
                    "emergency_reserve",
                    "risk_profile",
                    "updated_at",
                ),
            )
            for item in profiles
        ],
    }


async def current_financial_state(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    normalized_inputs = await build_normalized_inputs(
        session, household_id=household_id, user_id=user_id
    )
    return calculate_financial_state(
        normalized_inputs,
        evaluated_at=evaluated_at,
    )


def _json_safe(value: Any) -> Any:
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def _fingerprint(value: Any) -> str:
    canonical = json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def create_snapshot(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    idempotency_key: str | None,
    evaluated_at: datetime | None = None,
    commit: bool = True,
) -> FinancialStateSnapshot:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    if idempotency_key:
        existing_result = await session.execute(
            select(FinancialStateSnapshot).where(
                FinancialStateSnapshot.household_id == household_id,
                FinancialStateSnapshot.idempotency_key == idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing is not None:
            return existing
    evaluated_at = evaluated_at or datetime.now(timezone.utc)
    normalized_inputs = await build_normalized_inputs(
        session, household_id=household_id, user_id=user_id
    )
    state = calculate_financial_state(
        normalized_inputs,
        evaluated_at=evaluated_at,
    )
    snapshot = FinancialStateSnapshot(
        household_id=household_id,
        created_by_user_id=user_id,
        evaluated_at=evaluated_at,
        engine_version=state["engine_version"],
        normalized_inputs=_json_safe(normalized_inputs),
        metrics=_json_safe(state["metrics"]),
        member_views=_json_safe(state["member_views"]),
        data_quality=state["data_quality"],
        confidence=state["confidence"],
        missing_fields=state["missing_fields"],
        inconsistencies=state["inconsistencies"],
        input_fingerprint=_fingerprint(normalized_inputs),
        idempotency_key=idempotency_key,
    )
    session.add(snapshot)
    if not commit:
        await session.flush()
        await session.refresh(snapshot)
        return snapshot
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        if not idempotency_key:
            raise
        concurrent_result = await session.execute(
            select(FinancialStateSnapshot).where(
                FinancialStateSnapshot.household_id == household_id,
                FinancialStateSnapshot.idempotency_key == idempotency_key,
            )
        )
        concurrent = concurrent_result.scalar_one_or_none()
        if concurrent is None:
            raise
        return concurrent
    await session.refresh(snapshot)
    return snapshot


async def snapshot_history(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    total_result = await session.execute(
        select(func.count(FinancialStateSnapshot.id)).where(
            FinancialStateSnapshot.household_id == household_id
        )
    )
    result = await session.execute(
        select(FinancialStateSnapshot)
        .where(FinancialStateSnapshot.household_id == household_id)
        .order_by(
            FinancialStateSnapshot.evaluated_at.desc(),
            FinancialStateSnapshot.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return {"items": list(result.scalars().all()), "total": int(total_result.scalar_one())}


async def get_snapshot(
    session: AsyncSession,
    *,
    household_id: int,
    snapshot_id: int,
    user_id: int,
) -> FinancialStateSnapshot:
    await get_household_access(session, household_id=household_id, user_id=user_id)
    result = await session.execute(
        select(FinancialStateSnapshot).where(
            FinancialStateSnapshot.id == snapshot_id,
            FinancialStateSnapshot.household_id == household_id,
        )
    )
    snapshot = result.scalar_one_or_none()
    if snapshot is None:
        raise FinancialResourceNotFoundError("snapshot not found")
    return snapshot
