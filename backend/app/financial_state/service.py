from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, TypeVar

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import User
from backend.app.catalog.models import AssetCatalog
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial_state.engine import calculate_financial_state
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    Household,
    HouseholdMember,
    OwnedAsset,
)


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
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "ARCHIVED" and household.household_type == "PERSONAL":
        raise HouseholdConflictError("personal household cannot be archived")
    for field, value in values.items():
        if value is not None:
            setattr(household, field, value)
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
        .where(HouseholdMember.household_id == household_id)
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


async def add_member(
    session: AsyncSession,
    *,
    household_id: int,
    user_id: int,
    payload: Any,
) -> dict[str, Any]:
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    if household.household_type != "SHARED":
        raise HouseholdConflictError("personal household cannot accept members")
    result = await session.execute(
        select(User).where(User.email == str(payload.email).lower(), User.is_active.is_(True))
    )
    invited_user = result.scalar_one_or_none()
    if invited_user is None:
        raise FinancialResourceNotFoundError("user not found")
    existing_result = await session.execute(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == invited_user.id,
        )
    )
    membership = existing_result.scalar_one_or_none()
    if membership is not None and membership.status == "ACTIVE":
        raise HouseholdConflictError("user is already a household member")
    if payload.is_default:
        await _clear_user_default(session, user_id=invited_user.id)
    if membership is None:
        membership = HouseholdMember(
            household_id=household_id,
            user_id=invited_user.id,
            role=payload.role,
            status="ACTIVE",
            is_default=payload.is_default,
        )
        session.add(membership)
    else:
        membership.role = payload.role
        membership.status = "ACTIVE"
        membership.is_default = payload.is_default
    await session.commit()
    await session.refresh(membership)
    return await _member_read(session, membership)


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


async def update_member(
    session: AsyncSession,
    *,
    household_id: int,
    member_id: int,
    user_id: int,
    payload: Any,
) -> dict[str, Any]:
    household, _ = await require_household_owner(
        session, household_id=household_id, user_id=user_id
    )
    result = await session.execute(
        select(HouseholdMember).where(
            HouseholdMember.id == member_id,
            HouseholdMember.household_id == household_id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise FinancialResourceNotFoundError("member not found")
    values = payload.model_dump(exclude_unset=True)
    removes_owner = membership.role == "OWNER" and (
        values.get("role") == "MEMBER" or values.get("status") == "REMOVED"
    )
    if removes_owner and await _active_owner_count(
        session,
        household_id=household_id,
        excluding_member_id=membership.id,
    ) == 0:
        raise HouseholdConflictError("household must retain an active owner")
    if household.household_type == "PERSONAL" and values.get("status") == "REMOVED":
        raise HouseholdConflictError("personal household owner cannot be removed")
    if values.get("is_default") is True:
        await _clear_user_default(
            session,
            user_id=membership.user_id,
            except_membership_id=membership.id,
        )
    for field, value in values.items():
        if value is not None:
            setattr(membership, field, value)
    if membership.status == "REMOVED":
        membership.is_default = False
        await _restore_personal_default(session, user_id=membership.user_id)
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
    class Removal:
        @staticmethod
        def model_dump(*, exclude_unset: bool = False) -> dict[str, str]:
            return {"status": "REMOVED"}

    await update_member(
        session,
        household_id=household_id,
        member_id=member_id,
        user_id=user_id,
        payload=Removal(),
    )


async def _get_record(
    session: AsyncSession,
    model: type[ResourceModel],
    *,
    household_id: int,
    record_id: int,
) -> ResourceModel:
    result = await session.execute(
        select(model).where(model.id == record_id, model.household_id == household_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
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
    await get_household_access(session, household_id=household_id, user_id=user_id)
    values = payload.model_dump()
    if model is OwnedAsset:
        await _validate_catalog_reference(
            session, asset_catalog_id=values.get("asset_catalog_id")
        )
    record = model(household_id=household_id, user_id=user_id, **values)
    session.add(record)
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
        select(model).where(model.household_id == household_id).order_by(model.id.desc())
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
    return await _get_record(
        session, model, household_id=household_id, record_id=record_id
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
    _, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    record = await _get_record(
        session, model, household_id=household_id, record_id=record_id
    )
    if not _can_mutate_record(record, membership, user_id):
        raise HouseholdPermissionError("financial resource permission denied")
    values = payload.model_dump(exclude_unset=True)
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
    _, membership = await get_household_access(
        session, household_id=household_id, user_id=user_id
    )
    record = await _get_record(
        session, model, household_id=household_id, record_id=record_id
    )
    if not _can_mutate_record(record, membership, user_id):
        raise HouseholdPermissionError("financial resource permission denied")
    await session.delete(record)
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
    member_ids = [
        item["user_id"] for item in members if item["status"] == "ACTIVE"
    ]

    async def load(model: Any) -> list[Any]:
        result = await session.execute(
            select(model).where(model.household_id == household_id).order_by(model.id.asc())
        )
        return list(result.scalars().all())

    incomes = await load(Income)
    expenses = await load(Expense)
    liabilities = await load(FinancialLiability)
    assets = await load(OwnedAsset)
    goals = await load(FinancialGoal)
    profile_result = await session.execute(
        select(FinancialProfile).where(FinancialProfile.user_id.in_(member_ids))
    )
    profiles = list(profile_result.scalars().all())
    return {
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
    evaluated_at = datetime.now(timezone.utc)
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
