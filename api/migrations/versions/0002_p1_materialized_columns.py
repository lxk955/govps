"""P1 物化列：聚合键 / 搜索文本 / 三项评分与理由（refactor-plan §2 #1/#9）。

Revision ID: 0002_p1_materialized_columns
Revises: 0001_legacy_baseline
Create Date: 2026-08-24

全部为可空增量列：旧代码不读即无害，回滚无需 DB 动作（§4）。
存量旧库的列值由扫描收尾 refresh_derived_fields 全量回填，无需在此搬数据。
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_p1_materialized_columns"
down_revision = "0001_legacy_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("spec_key", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("search_text", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("line_tags_text", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("hot_score", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("deal_score", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("popularity_score", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("score_reasons", sa.JSON(), nullable=True))
    # /go 与列表聚合水合路径：WHERE merchant_id = ? AND spec_key = ?
    op.create_index(
        "ix_products_merchant_spec",
        "products",
        ["merchant_id", "spec_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_products_merchant_spec", table_name="products")
    for col in (
        "score_reasons",
        "popularity_score",
        "deal_score",
        "hot_score",
        "line_tags_text",
        "search_text",
        "spec_key",
    ):
        op.drop_column("products", col)
