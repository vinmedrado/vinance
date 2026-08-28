"""conversational advisor learning profile

Revision ID: 20260508_0016
Revises: 20260508_0013
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0016"
down_revision = "20260508_0013"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("user_learning_profiles"):
        op.create_table(
            "user_learning_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("financial_literacy_level", sa.String(length=40), nullable=False, server_default="beginner"),
            sa.Column("preferred_tone", sa.String(length=40), nullable=False, server_default="consultive"),
            sa.Column("preferred_detail_level", sa.String(length=40), nullable=False, server_default="short"),
            sa.Column("observed_risk_behavior", sa.String(length=40), nullable=False, server_default="balanced"),
            sa.Column("recurring_challenges", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("engagement_score", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_user_learning_profiles_org_user"),
        )
        op.create_index("ix_user_learning_profiles_org_user", "user_learning_profiles", ["organization_id", "user_id"])

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_learning_profiles"):
        op.drop_index("ix_user_learning_profiles_org_user", table_name="user_learning_profiles")
        op.drop_table("user_learning_profiles")
