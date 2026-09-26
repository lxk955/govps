"""在 users 表中添加 monitor_share_ip_mode 并在 user_nodes 表中添加 public_ip 字段。

Revision ID: 0018_node_public_ip_and_share_mode
Revises: 0017_traffic_cycle_fields
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0018_node_public_ip_and_share_mode"
down_revision = "0017_traffic_cycle_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_share_ip_mode" not in user_cols:
        op.add_column(
            "users",
            sa.Column(
                "monitor_share_ip_mode",
                sa.String(20),
                server_default=sa.text("'mask'"),
                nullable=False,
            ),
        )

    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "public_ip" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "public_ip",
                sa.String(64),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_share_ip_mode" in user_cols:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("monitor_share_ip_mode")

    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "public_ip" in node_cols:
        with op.batch_alter_table("user_nodes") as batch_op:
            batch_op.drop_column("public_ip")
