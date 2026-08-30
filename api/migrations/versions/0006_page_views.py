"""访问记录表：page_views（PV/UV 统计）。

Revision ID: 0006_page_views
Revises: 0005_request_rate_events
Create Date: 2026-08-30

前端在路由变化时上报，用于统计各页面访问量（如首页 vs 产品页的对比）。
route 为归一化路由；复合索引 (route, created_at) 服务按页面 + 时间范围统计，
session_id 索引服务 UV / 跳出率，created_at 索引服务时间窗查询。
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_page_views"
down_revision = "0005_request_rate_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "page_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route", sa.String(length=120), nullable=False),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ua", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_page_views_route", "page_views", ["route"], unique=False)
    op.create_index("ix_page_views_product_id", "page_views", ["product_id"], unique=False)
    op.create_index("ix_page_views_session_id", "page_views", ["session_id"], unique=False)
    op.create_index("ix_page_views_created_at", "page_views", ["created_at"], unique=False)
    op.create_index(
        "ix_page_views_route_created", "page_views", ["route", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_page_views_route_created", table_name="page_views")
    op.drop_index("ix_page_views_created_at", table_name="page_views")
    op.drop_index("ix_page_views_session_id", table_name="page_views")
    op.drop_index("ix_page_views_product_id", table_name="page_views")
    op.drop_index("ix_page_views_route", table_name="page_views")
    op.drop_table("page_views")
