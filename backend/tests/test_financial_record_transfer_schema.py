from backend.app.core.database import Base
from backend.app.financial_state.models import (  # noqa: F401
    FinancialRecordTransfer,
    FinancialRecordTransferItem,
)


def test_transfer_audit_tables_belong_to_canonical_metadata() -> None:
    assert "financial_record_transfers" in Base.metadata.tables
    assert "financial_record_transfer_items" in Base.metadata.tables

    batches = Base.metadata.tables["financial_record_transfers"]
    assert {
        "id",
        "actor_user_id",
        "target_household_id",
        "resource_type",
        "idempotency_key",
        "request_fingerprint",
        "record_count",
        "duplicate_reviewed",
        "status",
        "created_at",
    }.issubset(batches.columns.keys())

    items = Base.metadata.tables["financial_record_transfer_items"]
    assert {
        "id",
        "transfer_id",
        "resource_type",
        "resource_id",
        "owner_user_id",
        "source_household_id",
        "target_household_id",
        "source_ownership_scope",
        "target_ownership_scope",
        "before_data",
        "possible_duplicate_count",
        "created_at",
    }.issubset(items.columns.keys())

    unique_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in items.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("resource_type", "resource_id") in unique_sets
