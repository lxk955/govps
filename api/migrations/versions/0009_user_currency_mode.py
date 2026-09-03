"""用户偏好新增货币模式字段：currency_mode。

Revision ID: 0009_user_currency_mode
Revises: 0008_dns_leak_hits
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_user_currency_mode"
down_revision = "0008_dns_leak_hits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("currency_mode", sa.String(length=20), server_default="CNY", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "currency_mode")
