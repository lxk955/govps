"""在 users 和 user_nodes 表中添加 VPS 到期提醒配置与阶段记录字段。

Revision ID: 0015_monitor_expiration_reminder
Revises: 0014_user_nodes_is_public
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0015_monitor_expiration_reminder"
down_revision = "0014_user_nodes_is_public"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. users 表新增全局到期提醒配置
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_expire_notify_enabled" not in user_cols:
        op.add_column(
            "users",
            sa.Column(
                "monitor_expire_notify_enabled",
                sa.Boolean(),
                server_default=sa.text("1"),
                nullable=False,
            ),
        )
    if "monitor_expire_stages" not in user_cols:
        op.add_column(
            "users",
            sa.Column(
                "monitor_expire_stages",
                sa.JSON(),
                server_default=sa.text("'[15, 7, 3, 1]'"),
                nullable=False,
            ),
        )

    # 2. user_nodes 表新增节点级到期提醒配置与已通知阶段
    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "expire_notify_enabled" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column("expire_notify_enabled", sa.Boolean(), nullable=True),
        )
    if "expire_notify_stages" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column("expire_notify_stages", sa.JSON(), nullable=True),
        )
    if "notified_expire_stages" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "notified_expire_stages",
                sa.JSON(),
                server_default=sa.text("'[]'"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "notified_expire_stages" in node_cols:
        op.drop_column("user_nodes", "notified_expire_stages")
    if "expire_notify_stages" in node_cols:
        op.drop_column("user_nodes", "expire_notify_stages")
    if "expire_notify_enabled" in node_cols:
        op.drop_column("user_nodes", "expire_notify_enabled")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_expire_stages" in user_cols:
        op.drop_column("users", "monitor_expire_stages")
    if "monitor_expire_notify_enabled" in user_cols:
        op.drop_column("users", "monitor_expire_notify_enabled")
