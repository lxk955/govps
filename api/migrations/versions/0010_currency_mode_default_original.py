"""币种偏好默认改为原币（original）。

Revision ID: 0010_currency_mode_default_original
Revises: 0009_user_currency_mode
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_currency_mode_default_original"
down_revision = "0009_user_currency_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "currency_mode",
            existing_type=sa.String(length=20),
            server_default="original",
            existing_nullable=False,
        )
    # 旧默认 CNY 并非用户主动选择（偏好 PUT 之前写不进库），一并改回原币
    op.execute(sa.text("UPDATE users SET currency_mode = 'original' WHERE currency_mode = 'CNY'"))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "currency_mode",
            existing_type=sa.String(length=20),
            server_default="CNY",
            existing_nullable=False,
        )
