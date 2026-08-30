"""详情曲线查询：快照表 (product_id, checked_at) 复合索引。

Revision ID: 0007_snapshot_checked_indexes
Revises: 0006_page_views
Create Date: 2026-08-30

GET /api/products/{id} 按 product_id + checked_at 窗口取最近 N 点。
原先只有 product_id 单列索引，复合索引覆盖该过滤与排序。
"""

from alembic import op

revision = "0007_snapshot_checked_indexes"
down_revision = "0006_page_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_price_snapshots_product_checked",
        "price_snapshots",
        ["product_id", "checked_at"],
        unique=False,
    )
    op.create_index(
        "ix_stock_snapshots_product_checked",
        "stock_snapshots",
        ["product_id", "checked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stock_snapshots_product_checked", table_name="stock_snapshots")
    op.drop_index("ix_price_snapshots_product_checked", table_name="price_snapshots")
