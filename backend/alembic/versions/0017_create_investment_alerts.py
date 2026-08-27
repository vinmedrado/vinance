"""create investment monitoring subscriptions, states and in-app alerts

Revision ID: 0017_investment_alerts
Revises: 0016_decision_performance
Create Date: 2026-08-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017_investment_alerts"
down_revision = "0016_decision_performance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_alert_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset", sa.String(length=32), nullable=False),
        sa.Column("market", sa.String(length=24), nullable=False),
        sa.Column("budget", sa.Numeric(18, 2), nullable=False),
        sa.Column("investor_profile", sa.String(length=32), nullable=False),
        sa.Column("include_warnings", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trend_filter", sa.String(length=32), nullable=True),
        sa.Column("source_decision_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_on_action_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_on_score_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_on_confidence_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_on_risk_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("alert_on_new_opportunity", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("minimum_score_delta", sa.Numeric(8, 4), nullable=False, server_default="5"),
        sa.Column("minimum_confidence_delta", sa.Numeric(8, 4), nullable=False, server_default="10"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("rule_version", sa.String(length=80), nullable=False, server_default="investment-alerts-v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "minimum_score_delta >= 1 AND minimum_score_delta <= 100",
            name="ck_alert_subscriptions_score_delta",
        ),
        sa.CheckConstraint(
            "minimum_confidence_delta >= 1 AND minimum_confidence_delta <= 100",
            name="ck_alert_subscriptions_confidence_delta",
        ),
        sa.CheckConstraint(
            "cooldown_minutes >= 30 AND cooldown_minutes <= 10080",
            name="ck_alert_subscriptions_cooldown",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_decision_id"],
            ["investment_decision_audits.decision_id"],
            name="fk_alert_subscriptions_source_decision",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "asset", name="uq_alert_subscriptions_user_asset"),
    )
    op.create_index(
        "ix_alert_subscriptions_user_enabled",
        "investment_alert_subscriptions",
        ["user_id", "enabled"],
    )
    op.create_index(
        "ix_alert_subscriptions_enabled_updated",
        "investment_alert_subscriptions",
        ["enabled", "updated_at"],
    )

    op.create_table(
        "investment_alert_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("asset", sa.String(length=32), nullable=False),
        sa.Column("last_decision_id", sa.String(length=36), nullable=True),
        sa.Column("last_action", sa.String(length=24), nullable=True),
        sa.Column("last_score", sa.Numeric(8, 4), nullable=True),
        sa.Column("last_confidence", sa.Numeric(8, 4), nullable=True),
        sa.Column("last_risk_level", sa.String(length=24), nullable=True),
        sa.Column("last_trend", sa.String(length=32), nullable=True),
        sa.Column("last_evaluation_key", sa.String(length=64), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluations_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_generated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cooldown_suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_prevented_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("volume_suppressed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["investment_alert_subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["last_decision_id"],
            ["investment_decision_audits.decision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subscription_id", name="uq_alert_states_subscription"),
        sa.UniqueConstraint("user_id", "asset", name="uq_alert_states_user_asset"),
    )
    op.create_index(
        "ix_alert_states_user_checked",
        "investment_alert_states",
        ["user_id", "last_checked_at"],
    )

    op.create_table(
        "investment_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("alert_id", sa.String(length=36), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=True),
        sa.Column("decision_id", sa.String(length=36), nullable=False),
        sa.Column("asset", sa.String(length=32), nullable=False),
        sa.Column("alert_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("delivery_channel", sa.String(length=16), nullable=False, server_default="IN_APP"),
        sa.Column("previous_state", sa.JSON(), nullable=False),
        sa.Column("current_state", sa.JSON(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("rule_version", sa.String(length=80), nullable=False, server_default="investment-alerts-v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "alert_type IN ('NEW_OPPORTUNITY','ACTION_CHANGE','SCORE_CHANGE','CONFIDENCE_CHANGE','RISK_CHANGE')",
            name="ck_investment_alerts_type",
        ),
        sa.CheckConstraint(
            "severity IN ('INFO','MEDIUM','HIGH')",
            name="ck_investment_alerts_severity",
        ),
        sa.CheckConstraint("delivery_channel = 'IN_APP'", name="ck_investment_alerts_channel"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["investment_alert_subscriptions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["investment_decision_audits.decision_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", name="uq_investment_alerts_alert_id"),
        sa.UniqueConstraint("deduplication_key", name="uq_investment_alerts_deduplication_key"),
    )
    op.create_index("ix_investment_alerts_user_created", "investment_alerts", ["user_id", "created_at"])
    op.create_index(
        "ix_investment_alerts_user_read_created",
        "investment_alerts",
        ["user_id", "read_at", "created_at"],
    )
    op.create_index("ix_investment_alerts_user_asset", "investment_alerts", ["user_id", "asset", "created_at"])
    op.create_index("ix_investment_alerts_user_type", "investment_alerts", ["user_id", "alert_type", "created_at"])
    op.create_index("ix_investment_alerts_user_severity", "investment_alerts", ["user_id", "severity", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_investment_alerts_user_severity", table_name="investment_alerts")
    op.drop_index("ix_investment_alerts_user_type", table_name="investment_alerts")
    op.drop_index("ix_investment_alerts_user_asset", table_name="investment_alerts")
    op.drop_index("ix_investment_alerts_user_read_created", table_name="investment_alerts")
    op.drop_index("ix_investment_alerts_user_created", table_name="investment_alerts")
    op.drop_table("investment_alerts")
    op.drop_index("ix_alert_states_user_checked", table_name="investment_alert_states")
    op.drop_table("investment_alert_states")
    op.drop_index("ix_alert_subscriptions_enabled_updated", table_name="investment_alert_subscriptions")
    op.drop_index("ix_alert_subscriptions_user_enabled", table_name="investment_alert_subscriptions")
    op.drop_table("investment_alert_subscriptions")
