"""add audited personal-to-household financial record transfers

Revision ID: 0028_financial_record_transfers
Revises: 0027_auth_sessions
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0028_financial_record_transfers"
down_revision = "0027_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_record_transfers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("target_household_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column(
            "duplicate_reviewed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="COMMITTED",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_type IN ('INCOME','EXPENSE')",
            name="ck_financial_record_transfers_resource_type",
        ),
        sa.CheckConstraint(
            "record_count BETWEEN 1 AND 100",
            name="ck_financial_record_transfers_record_count",
        ),
        sa.CheckConstraint(
            "status = 'COMMITTED'",
            name="ck_financial_record_transfers_status",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_user_id",
            "idempotency_key",
            name="uq_financial_record_transfers_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_financial_record_transfers_actor_created",
        "financial_record_transfers",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_financial_record_transfers_target_created",
        "financial_record_transfers",
        ["target_household_id", "created_at"],
    )

    op.create_table(
        "financial_record_transfer_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transfer_id", sa.Integer(), nullable=False),
        sa.Column("resource_type", sa.String(length=16), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("source_household_id", sa.Integer(), nullable=False),
        sa.Column("target_household_id", sa.Integer(), nullable=False),
        sa.Column("source_ownership_scope", sa.String(length=16), nullable=False),
        sa.Column("target_ownership_scope", sa.String(length=16), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=False),
        sa.Column(
            "possible_duplicate_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_type IN ('INCOME','EXPENSE')",
            name="ck_financial_record_transfer_items_resource_type",
        ),
        sa.CheckConstraint(
            "source_ownership_scope = 'PERSONAL'",
            name="ck_financial_record_transfer_items_source_scope",
        ),
        sa.CheckConstraint(
            "target_ownership_scope = 'HOUSEHOLD'",
            name="ck_financial_record_transfer_items_target_scope",
        ),
        sa.CheckConstraint(
            "possible_duplicate_count >= 0",
            name="ck_financial_record_transfer_items_duplicate_count",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["target_household_id"], ["households.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["transfer_id"], ["financial_record_transfers.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "resource_type",
            "resource_id",
            name="uq_financial_record_transfer_items_resource",
        ),
    )
    op.create_index(
        "ix_financial_record_transfer_items_transfer",
        "financial_record_transfer_items",
        ["transfer_id", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_financial_record_transfer_items_transfer",
        table_name="financial_record_transfer_items",
    )
    op.drop_table("financial_record_transfer_items")
    op.drop_index(
        "ix_financial_record_transfers_target_created",
        table_name="financial_record_transfers",
    )
    op.drop_index(
        "ix_financial_record_transfers_actor_created",
        table_name="financial_record_transfers",
    )
    op.drop_table("financial_record_transfers")
