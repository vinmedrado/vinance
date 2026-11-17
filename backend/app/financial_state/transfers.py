from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, TypeVar

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.models import User
from backend.app.financial.models import Expense, Income
from backend.app.financial_state import service
from backend.app.financial_state.models import (
    FinancialRecordTransfer,
    FinancialRecordTransferItem,
    Household,
    HouseholdMember,
)


TransferModel = TypeVar("TransferModel", Income, Expense)


def _resource_type(model: type[TransferModel]) -> str:
    if model is Income:
        return "INCOME"
    if model is Expense:
        return "EXPENSE"
    raise service.FinancialStateValidationError("resource type cannot be transferred")


def _effective_date(record: Income | Expense) -> date:
    return record.received_at if isinstance(record, Income) else record.due_date


def _semantic_key(record: Income | Expense) -> tuple[Any, ...]:
    common = (
        Decimal(str(record.amount)),
        _effective_date(record),
        record.description.strip().casefold(),
        bool(record.is_recurring),
    )
    if isinstance(record, Income):
        return (*common, record.income_type.strip().casefold())
    return (*common, record.category.strip().casefold())


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _before_data(record: Income | Expense) -> dict[str, Any]:
    names = (
        (
            "id",
            "user_id",
            "household_id",
            "ownership_scope",
            "description",
            "amount",
            "income_type",
            "received_at",
            "is_recurring",
            "created_at",
            "updated_at",
        )
        if isinstance(record, Income)
        else (
            "id",
            "user_id",
            "household_id",
            "ownership_scope",
            "description",
            "amount",
            "category",
            "due_date",
            "paid_at",
            "is_paid",
            "is_recurring",
            "expense_nature",
            "created_at",
            "updated_at",
        )
    )
    return {name: _json_value(getattr(record, name)) for name in names}


def _request_fingerprint(
    *,
    resource_type: str,
    target_household_id: int,
    user_id: int,
    record_ids: list[int],
    duplicate_reviewed: bool,
) -> str:
    canonical = json.dumps(
        {
            "resource_type": resource_type,
            "target_household_id": target_household_id,
            "user_id": user_id,
            "record_ids": sorted(record_ids),
            "duplicate_reviewed": duplicate_reviewed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _target_access_locked(
    session: AsyncSession,
    *,
    target_household_id: int,
    user_id: int,
    lock: bool = True,
) -> tuple[Household, HouseholdMember]:
    statement = (
        select(Household, HouseholdMember)
        .join(HouseholdMember, HouseholdMember.household_id == Household.id)
        .where(
            Household.id == target_household_id,
            Household.household_type == "SHARED",
            Household.status == "ACTIVE",
            HouseholdMember.user_id == user_id,
            HouseholdMember.status == "ACTIVE",
        )
    )
    if lock:
        statement = statement.with_for_update(of=(Household, HouseholdMember))
    result = await session.execute(statement)
    row = result.first()
    if row is None:
        # Do not disclose whether the household exists to a non-member.
        raise service.HouseholdNotFoundError("shared household not found")
    return row[0], row[1]


async def _personal_records(
    session: AsyncSession,
    model: type[TransferModel],
    *,
    user_id: int,
    record_ids: list[int],
    lock: bool,
) -> list[TransferModel]:
    statement = (
        select(model)
        .join(Household, Household.id == model.household_id)
        .join(
            HouseholdMember,
            and_(
                HouseholdMember.household_id == model.household_id,
                HouseholdMember.user_id == user_id,
            ),
        )
        .where(
            model.id.in_(record_ids),
            model.user_id == user_id,
            model.ownership_scope == "PERSONAL",
            Household.status == "ACTIVE",
            HouseholdMember.status == "ACTIVE",
        )
        .order_by(model.id.asc())
    )
    if lock:
        # Household locks are acquired first by transfer_records. Locking only
        # the financial rows here preserves that global lock order.
        statement = statement.with_for_update(of=model)
    result = await session.execute(statement)
    records = list(result.scalars().all())
    if len(records) != len(record_ids):
        raise service.FinancialResourceNotFoundError("personal financial resource not found")
    return records


async def _duplicate_map(
    session: AsyncSession,
    model: type[TransferModel],
    *,
    target_household_id: int,
    records: list[TransferModel],
) -> dict[int, list[TransferModel]]:
    date_column = Income.received_at if model is Income else Expense.due_date
    candidates_filter = [
        and_(model.amount == record.amount, date_column == _effective_date(record))
        for record in records
    ]
    statement = select(model).where(
        model.household_id == target_household_id,
        model.ownership_scope == "HOUSEHOLD",
        or_(*candidates_filter),
    )
    result = await session.execute(statement)
    candidates = list(result.scalars().all())
    by_key: dict[tuple[Any, ...], list[TransferModel]] = {}
    for candidate in candidates:
        by_key.setdefault(_semantic_key(candidate), []).append(candidate)
    return {
        record.id: sorted(by_key.get(_semantic_key(record), []), key=lambda item: item.id)
        for record in records
    }


def _preview_payload(
    *,
    resource_type: str,
    target_household_id: int,
    records: list[Income | Expense],
    duplicates: dict[int, list[Income | Expense]],
) -> dict[str, Any]:
    items = []
    for record in records:
        items.append(
            {
                "record_id": record.id,
                "source_household_id": record.household_id,
                "description": record.description,
                "amount": record.amount,
                "effective_date": _effective_date(record),
                "possible_duplicates": [
                    {
                        "candidate_id": candidate.id,
                        "description": candidate.description,
                        "amount": candidate.amount,
                        "effective_date": _effective_date(candidate),
                    }
                    for candidate in duplicates[record.id]
                ],
            }
        )
    return {
        "resource_type": resource_type,
        "target_household_id": target_household_id,
        "record_count": len(records),
        "requires_duplicate_review": any(duplicates.values()),
        "items": items,
    }


async def preview_records(
    session: AsyncSession,
    *,
    model: type[TransferModel],
    target_household_id: int,
    user_id: int,
    record_ids: list[int],
) -> dict[str, Any]:
    await _target_access_locked(
        session,
        target_household_id=target_household_id,
        user_id=user_id,
        lock=False,
    )
    records = await _personal_records(
        session,
        model,
        user_id=user_id,
        record_ids=record_ids,
        lock=False,
    )
    duplicates = await _duplicate_map(
        session,
        model,
        target_household_id=target_household_id,
        records=records,
    )
    return _preview_payload(
        resource_type=_resource_type(model),
        target_household_id=target_household_id,
        records=records,
        duplicates=duplicates,
    )


async def _existing_transfer_response(
    session: AsyncSession,
    *,
    transfer: FinancialRecordTransfer,
    request_fingerprint: str,
) -> dict[str, Any]:
    if transfer.request_fingerprint != request_fingerprint:
        raise service.HouseholdConflictError(
            "idempotency key was already used with a different transfer"
        )
    result = await session.execute(
        select(FinancialRecordTransferItem)
        .where(FinancialRecordTransferItem.transfer_id == transfer.id)
        .order_by(FinancialRecordTransferItem.id.asc())
    )
    items = list(result.scalars().all())
    return {
        "transfer_id": transfer.id,
        "resource_type": transfer.resource_type,
        "target_household_id": transfer.target_household_id,
        "record_count": transfer.record_count,
        "moved_record_ids": [item.resource_id for item in items],
        "source_household_ids": sorted({item.source_household_id for item in items}),
        "status": transfer.status,
        "replayed": True,
        "created_at": transfer.created_at,
    }


async def _find_existing_transfer(
    session: AsyncSession,
    *,
    user_id: int,
    idempotency_key: str,
) -> FinancialRecordTransfer | None:
    result = await session.execute(
        select(FinancialRecordTransfer).where(
            FinancialRecordTransfer.actor_user_id == user_id,
            FinancialRecordTransfer.idempotency_key == idempotency_key,
        )
    )
    return result.scalar_one_or_none()


async def _eligible_source_household_ids(
    session: AsyncSession,
    model: type[TransferModel],
    *,
    user_id: int,
    record_ids: list[int],
) -> set[int]:
    """Discover lock scope without treating a concurrent replay as missing."""

    result = await session.execute(
        select(model.household_id)
        .join(Household, Household.id == model.household_id)
        .join(
            HouseholdMember,
            and_(
                HouseholdMember.household_id == model.household_id,
                HouseholdMember.user_id == user_id,
            ),
        )
        .where(
            model.id.in_(record_ids),
            model.user_id == user_id,
            model.ownership_scope == "PERSONAL",
            Household.status == "ACTIVE",
            HouseholdMember.status == "ACTIVE",
        )
    )
    return {int(household_id) for household_id in result.scalars().all()}


async def _lock_transfer_scope(
    session: AsyncSession,
    *,
    household_ids: set[int],
    user_id: int,
) -> None:
    """Use the same deterministic Household -> User order as membership flows."""

    await session.execute(
        select(Household.id)
        .where(Household.id.in_(sorted(household_ids)))
        .order_by(Household.id.asc())
        .with_for_update(of=Household, key_share=True)
    )
    await session.execute(
        select(User.id)
        .where(User.id == user_id)
        .with_for_update(of=User, key_share=True)
    )


async def transfer_records(
    session: AsyncSession,
    *,
    model: type[TransferModel],
    target_household_id: int,
    user_id: int,
    record_ids: list[int],
    duplicate_reviewed: bool,
    idempotency_key: str,
) -> dict[str, Any]:
    resource_type = _resource_type(model)
    if not 1 <= len(record_ids) <= 100 or len(set(record_ids)) != len(record_ids):
        raise service.FinancialStateValidationError(
            "record_ids must contain between 1 and 100 unique identifiers"
        )
    if any(record_id <= 0 for record_id in record_ids):
        raise service.FinancialStateValidationError("record_ids must be positive")
    normalized_key = idempotency_key.strip()
    if not normalized_key or len(normalized_key) > 128:
        raise service.FinancialStateValidationError("invalid Idempotency-Key")
    fingerprint = _request_fingerprint(
        resource_type=resource_type,
        target_household_id=target_household_id,
        user_id=user_id,
        record_ids=record_ids,
        duplicate_reviewed=duplicate_reviewed,
    )

    try:
        existing = await _find_existing_transfer(
            session,
            user_id=user_id,
            idempotency_key=normalized_key,
        )
        if existing is not None:
            return await _existing_transfer_response(
                session,
                transfer=existing,
                request_fingerprint=fingerprint,
            )

        source_household_ids = await _eligible_source_household_ids(
            session,
            model,
            user_id=user_id,
            record_ids=record_ids,
        )
        await _lock_transfer_scope(
            session,
            household_ids=source_household_ids | {target_household_id},
            user_id=user_id,
        )

        # A concurrent request can commit while this request waits for locks.
        # Re-read before validating records that may already have moved.
        existing = await _find_existing_transfer(
            session,
            user_id=user_id,
            idempotency_key=normalized_key,
        )
        if existing is not None:
            return await _existing_transfer_response(
                session,
                transfer=existing,
                request_fingerprint=fingerprint,
            )

        await _target_access_locked(
            session,
            target_household_id=target_household_id,
            user_id=user_id,
            lock=False,
        )
        records = await _personal_records(
            session,
            model,
            user_id=user_id,
            record_ids=record_ids,
            lock=True,
        )
        duplicates = await _duplicate_map(
            session,
            model,
            target_household_id=target_household_id,
            records=records,
        )
        if any(duplicates.values()) and not duplicate_reviewed:
            raise service.HouseholdConflictError(
                "possible duplicates require explicit review before transfer"
            )

        transfer = FinancialRecordTransfer(
            actor_user_id=user_id,
            target_household_id=target_household_id,
            resource_type=resource_type,
            idempotency_key=normalized_key,
            request_fingerprint=fingerprint,
            record_count=len(records),
            duplicate_reviewed=duplicate_reviewed,
            status="COMMITTED",
        )
        session.add(transfer)
        await session.flush()

        source_household_ids: set[int] = set()
        for record in records:
            source_household_id = int(record.household_id)
            source_household_ids.add(source_household_id)
            session.add(
                FinancialRecordTransferItem(
                    transfer_id=transfer.id,
                    resource_type=resource_type,
                    resource_id=record.id,
                    owner_user_id=user_id,
                    source_household_id=source_household_id,
                    target_household_id=target_household_id,
                    source_ownership_scope="PERSONAL",
                    target_ownership_scope="HOUSEHOLD",
                    before_data=_before_data(record),
                    possible_duplicate_count=len(duplicates[record.id]),
                )
            )
            record.household_id = target_household_id
            record.ownership_scope = "HOUSEHOLD"

        for household_id in sorted(source_household_ids | {target_household_id}):
            await service._mark_continuous_dirty(
                session,
                household_id=household_id,
                category="FINANCIAL_DATA",
            )
        await session.flush()
        await session.refresh(transfer)
        created_at = transfer.created_at
        await session.commit()
        return {
            "transfer_id": transfer.id,
            "resource_type": resource_type,
            "target_household_id": target_household_id,
            "record_count": len(records),
            "moved_record_ids": [record.id for record in records],
            "source_household_ids": sorted(source_household_ids),
            "status": "COMMITTED",
            "replayed": False,
            "created_at": created_at,
        }
    except Exception:
        await session.rollback()
        raise
