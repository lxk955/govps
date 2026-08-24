"""P7 #10 限流存储落地：request_rate_events 滑动窗口计数表。

Revision ID: 0005_request_rate_events
Revises: 0004_p7_scheduling_notify
Create Date: 2026-08-24

替代进程内 `_ip_requests` deque：多 worker / 重启后限流窗口仍连续。
复合索引覆盖窗口计数查询；created_at 单列索引服务于过期清理。
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_request_rate_events"
down_revision = "0004_p7_scheduling_notify"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "request_rate_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_request_rate_events_created_at",
        "request_rate_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_request_rate_events_ip_created",
        "request_rate_events",
        ["ip", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_request_rate_events_ip_created", table_name="request_rate_events")
    op.drop_index("ix_request_rate_events_created_at", table_name="request_rate_events")
    op.drop_table("request_rate_events")
