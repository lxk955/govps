"""管理后台站点配置表。

Revision ID: 0011_site_settings
Revises: 0010_currency_mode_default_original
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_site_settings"
down_revision = "0010_currency_mode_default_original"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "site_settings" not in inspector.get_table_names():
        op.create_table(
            "site_settings",
            sa.Column("key", sa.String(length=64), primary_key=True),
            sa.Column("value", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("site_settings")
