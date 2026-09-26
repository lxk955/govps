"""在 user_nodes 表中添加 expire_muted 字段用于静音当前周期提醒。

Revision ID: 0016_monitor_expire_muted
Revises: 0015_monitor_expiration_reminder
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_monitor_expire_muted"
down_revision = "0015_monitor_expiration_reminder"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "expire_muted" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "expire_muted",
                sa.Boolean(),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    if "expire_muted" in node_cols:
        with op.batch_alter_table("user_nodes") as batch_op:
            batch_op.drop_column("expire_muted")
