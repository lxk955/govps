"""P7 分级调度 + 邮件异步化列：merchants.crawl_interval_minutes / notify_logs.attempts。

Revision ID: 0004_p7_scheduling_notify
Revises: 0003_p5_exchange_rates
Create Date: 2026-08-24

均为可空增量列（§4 允许项）：
- crawl_interval_minutes：NULL 时回退 adapter 默认值 → 全局配置（scan.effective_interval_minutes）；
- attempts：NotifyLog 发送尝试计数，异步 worker 重试与终态判定依据。
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_p7_scheduling_notify"
down_revision = "0003_p5_exchange_rates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchants", sa.Column("crawl_interval_minutes", sa.Integer(), nullable=True))
    op.add_column("notify_logs", sa.Column("attempts", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("notify_logs", "attempts")
    op.drop_column("merchants", "crawl_interval_minutes")
