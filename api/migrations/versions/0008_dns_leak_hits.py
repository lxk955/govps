"""DNS 泄露检测命中记录表：dns_leak_hits。

Revision ID: 0008_dns_leak_hits
Revises: 0007_snapshot_checked_indexes
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_dns_leak_hits"
down_revision = "0007_snapshot_checked_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dns_leak_hits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("resolver_ip", sa.String(length=64), nullable=False),
        sa.Column("query_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_dns_leak_hits_token",
        "dns_leak_hits",
        ["token"],
        unique=False,
    )
    op.create_index(
        "ix_dns_leak_hits_resolver_ip",
        "dns_leak_hits",
        ["resolver_ip"],
        unique=False,
    )
    op.create_index(
        "ix_dns_leak_hits_created_at",
        "dns_leak_hits",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_dns_leak_hits_token_created",
        "dns_leak_hits",
        ["token", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dns_leak_hits_token_created", table_name="dns_leak_hits")
    op.drop_index("ix_dns_leak_hits_created_at", table_name="dns_leak_hits")
    op.drop_index("ix_dns_leak_hits_resolver_ip", table_name="dns_leak_hits")
    op.drop_index("ix_dns_leak_hits_token", table_name="dns_leak_hits")
    op.drop_table("dns_leak_hits")
