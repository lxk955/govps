"""爬虫执行历史流水记录表。

Revision ID: 0012_crawl_logs
Revises: 0011_site_settings
Create Date: 2026-09-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_crawl_logs"
down_revision = "0011_site_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "crawl_logs" not in inspector.get_table_names():
        op.create_table(
            "crawl_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("merchant_id", sa.Integer(), sa.ForeignKey("merchants.id"), nullable=True),
            sa.Column("merchant_name", sa.String(length=100), nullable=False),
            sa.Column("merchant_slug", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("method", sa.String(length=150), nullable=False),
            sa.Column("products_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("official_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("in_stock_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("message", sa.String(length=500), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_crawl_logs_merchant_id", "crawl_logs", ["merchant_id"])
        op.create_index("ix_crawl_logs_merchant_slug", "crawl_logs", ["merchant_slug"])
        op.create_index("ix_crawl_logs_status", "crawl_logs", ["status"])
        op.create_index("ix_crawl_logs_created_at", "crawl_logs", ["created_at"])
        op.create_index("ix_crawl_logs_slug_created", "crawl_logs", ["merchant_slug", "created_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "crawl_logs" in inspector.get_table_names():
        op.drop_table("crawl_logs")
