"""pre testing ai advisor memory rag analytics

Revision ID: 20260508_0017
Revises: 20260508_0016
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0017"
down_revision = "20260508_0016"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("advisor_conversations"):
        op.create_table(
            "advisor_conversations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_advisor_conversations_org_user", "advisor_conversations", ["organization_id", "user_id"])
    if not inspector.has_table("advisor_messages"):
        op.create_table(
            "advisor_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=True),
            sa.Column("role", sa.String(length=24), nullable=False),
            sa.Column("intent", sa.String(length=80), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_advisor_messages_org_user_created", "advisor_messages", ["organization_id", "user_id", "created_at"])
    if not inspector.has_table("advisor_memory_summaries"):
        op.create_table(
            "advisor_memory_summaries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("organization_id", "user_id", "conversation_id", name="uq_advisor_memory_org_user_conversation"),
        )
    if not inspector.has_table("ai_advisor_usage_logs"):
        op.create_table(
            "ai_advisor_usage_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("question_hash", sa.String(length=64), nullable=False),
            sa.Column("topic", sa.String(length=80), nullable=False, server_default="general"),
            sa.Column("intent", sa.String(length=80), nullable=False, server_default="open_financial_guidance"),
            sa.Column("provider", sa.String(length=40), nullable=False, server_default="local_fallback"),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("feedback", sa.String(length=20), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_ai_advisor_usage_org_created", "ai_advisor_usage_logs", ["organization_id", "created_at"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for index_name, table_name in [
        ("ix_ai_advisor_usage_org_created", "ai_advisor_usage_logs"),
        ("ix_advisor_messages_org_user_created", "advisor_messages"),
        ("ix_advisor_conversations_org_user", "advisor_conversations"),
    ]:
        if inspector.has_table(table_name):
            try:
                op.drop_index(index_name, table_name=table_name)
            except Exception:
                pass
    for table_name in ["ai_advisor_usage_logs", "advisor_memory_summaries", "advisor_messages", "advisor_conversations"]:
        if inspector.has_table(table_name):
            op.drop_table(table_name)
