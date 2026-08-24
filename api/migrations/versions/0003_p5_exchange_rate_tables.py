"""P5 汇率表：当前汇率 + 每日快照（refactor-plan §3 P5）。

Revision ID: 0003_p5_exchange_rates
Revises: 0002_p1_materialized_columns
Create Date: 2026-08-24

纯新增表（§4 允许项）。units_per_usd = 兑 1 美元所需该币种单位数；
USD = 外币金额 ÷ units_per_usd。unique(code, date) 保证快照按日幂等覆盖。
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_p5_exchange_rates"
down_revision = "0002_p1_materialized_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("units_per_usd", sa.Numeric(16, 8), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "exchange_rate_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("units_per_usd", sa.Numeric(16, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "date"),
    )
    op.create_index(
        "ix_exchange_rate_snapshots_code",
        "exchange_rate_snapshots",
        ["code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_exchange_rate_snapshots_code", table_name="exchange_rate_snapshots")
    op.drop_table("exchange_rate_snapshots")
    op.drop_table("exchange_rates")
