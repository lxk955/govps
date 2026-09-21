"""在 user_nodes 表中添加 is_public 节点公开监控控制字段。

Revision ID: 0014_user_nodes_is_public
Revises: 0013_user_nodes_and_snapshots
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0014_user_nodes_is_public"
down_revision = "0013_user_nodes_and_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "is_public" not in cols:
        op.add_column(
            "user_nodes",
            sa.Column("is_public", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        )
        op.create_index("ix_user_nodes_is_public", "user_nodes", ["is_public"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "is_public" in cols:
        indexes = {idx["name"] for idx in inspector.get_indexes("user_nodes")}
        if "ix_user_nodes_is_public" in indexes:
            op.drop_index("ix_user_nodes_is_public", table_name="user_nodes")
        op.drop_column("user_nodes", "is_public")
