"""consent-based household invitations

Revision ID: 0024_household_product_v1
Revises: 0023_continuous_autopilot_v1
Create Date: 2026-10-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0024_household_product_v1"
down_revision = "0023_continuous_autopilot_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "household_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("household_id", sa.Integer(), nullable=False),
        sa.Column("invited_email_normalized", sa.String(length=255), nullable=False),
        sa.Column("invited_user_id", sa.Integer(), nullable=True),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "invited_email_normalized = lower(invited_email_normalized)",
            name="ck_household_invitations_email_normalized",
        ),
        sa.CheckConstraint(
            "role IN ('OWNER','MEMBER')",
            name="ck_household_invitations_role",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','DECLINED','CANCELLED','EXPIRED')",
            name="ck_household_invitations_status",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["households.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invited_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_household_invitations_household_status",
        "household_invitations",
        ["household_id", "status"],
    )
    op.create_index(
        "ix_household_invitations_invitee_status",
        "household_invitations",
        ["invited_email_normalized", "status"],
    )
    op.create_index(
        "ix_household_invitations_invited_user_status",
        "household_invitations",
        ["invited_user_id", "status"],
    )
    op.create_index(
        "uq_household_invitations_pending_email",
        "household_invitations",
        ["household_id", "invited_email_normalized"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_household_invitations_pending_email",
        table_name="household_invitations",
    )
    op.drop_index(
        "ix_household_invitations_invited_user_status",
        table_name="household_invitations",
    )
    op.drop_index(
        "ix_household_invitations_invitee_status",
        table_name="household_invitations",
    )
    op.drop_index(
        "ix_household_invitations_household_status",
        table_name="household_invitations",
    )
    op.drop_table("household_invitations")
