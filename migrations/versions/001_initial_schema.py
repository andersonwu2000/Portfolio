"""Initial schema matching DataStore tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bars",
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("timestamp", sa.Text, nullable=False),
        sa.Column("freq", sa.Text, nullable=False, server_default="1d"),
        sa.Column("open", sa.Numeric, nullable=False),
        sa.Column("high", sa.Numeric, nullable=False),
        sa.Column("low", sa.Numeric, nullable=False),
        sa.Column("close", sa.Numeric, nullable=False),
        sa.Column("volume", sa.Numeric, nullable=False),
        sa.PrimaryKeyConstraint("symbol", "timestamp", "freq"),
    )

    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Text, nullable=False),
        sa.Column("strategy_id", sa.Text, nullable=False),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("side", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("price", sa.Numeric, nullable=False),
        sa.Column("commission", sa.Numeric, nullable=False),
        sa.Column("slippage_bps", sa.Numeric),
        sa.Column("executed_at", sa.Text, nullable=False),
        sa.Column("signal_value", sa.Numeric),
    )

    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("strategy_name", sa.Text, nullable=False),
        sa.Column("config", sa.Text, nullable=False),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("finished_at", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="running"),
        sa.Column("sharpe", sa.Numeric),
        sa.Column("max_drawdown", sa.Numeric),
        sa.Column("total_return", sa.Numeric),
        sa.Column("annual_return", sa.Numeric),
        sa.Column("detail", sa.Text),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.Text, nullable=False),
        sa.Column("rule_name", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("metric_value", sa.Numeric),
        sa.Column("threshold", sa.Numeric),
        sa.Column("action_taken", sa.Text, nullable=False),
        sa.Column("message", sa.Text),
    )


def downgrade() -> None:
    op.drop_table("risk_events")
    op.drop_table("backtest_results")
    op.drop_table("trades")
    op.drop_table("bars")
