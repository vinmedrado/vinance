"""PATCH 10 - estratégias avançadas e otimização

Revision ID: 20260429_0006
Revises: 20260429_0005
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = '20260429_0006'
down_revision = '20260429_0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('strategy_name', sa.String(length=64), nullable=False),
        sa.Column('asset_class', sa.String(length=32), nullable=True),
        sa.Column('start_date', sa.String(length=16), nullable=False),
        sa.Column('end_date', sa.String(length=16), nullable=False),
        sa.Column('mode', sa.String(length=32), nullable=False, server_default='grid_search'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
        sa.Column('params_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
    )
    op.create_table(
        'optimization_results',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(length=64), nullable=True),
        sa.Column('asset_class', sa.String(length=32), nullable=True),
        sa.Column('window_name', sa.String(length=64), nullable=True),
        sa.Column('train_start', sa.String(length=16), nullable=True),
        sa.Column('train_end', sa.String(length=16), nullable=True),
        sa.Column('test_start', sa.String(length=16), nullable=True),
        sa.Column('test_end', sa.String(length=16), nullable=True),
        sa.Column('parameters_json', sa.Text(), nullable=False),
        sa.Column('total_return', sa.Float(), nullable=True),
        sa.Column('annual_return', sa.Float(), nullable=True),
        sa.Column('max_drawdown', sa.Float(), nullable=True),
        sa.Column('sharpe_ratio', sa.Float(), nullable=True),
        sa.Column('win_rate', sa.Float(), nullable=True),
        sa.Column('total_trades', sa.Integer(), nullable=True),
        sa.Column('score_robustez', sa.Float(), nullable=True),
        sa.Column('warnings_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_optimization_results_run', 'optimization_results', ['run_id', 'score_robustez'])


def downgrade():
    op.drop_index('ix_optimization_results_run', table_name='optimization_results')
    op.drop_table('optimization_results')
    op.drop_table('optimization_runs')
