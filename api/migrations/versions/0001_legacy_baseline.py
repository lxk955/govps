"""legacy baseline：Alembic 引入前的存量库结构（旧仓 models + 六条手写 ALTER 后的最终形态）。

Revision ID: 0001_legacy_baseline
Revises:
Create Date: 2026-08-24

边界（refactor-plan §2 #8 / §4）：本迁移 = 旧部署「已运行过旧版 startup 补列链」后的结构。
此后所有增量（P1 物化列、P5 汇率表、P7 调度/通知/限流）走独立版本化迁移，
startup 的手写 ALTER 链同步废除。

对存量旧库不执行本迁移的 DDL（db_migrations.run_migrations 检测到
「有业务表且无 alembic_version」时直接 stamp 本版本），仅作为空库从零构建的起点。
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_legacy_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=False),
        sa.Column("aff_url_template", sa.String(length=500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_merchants_slug", "merchants", ["slug"], unique=True)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=True),
        sa.Column("ram_gb", sa.Numeric(6, 1), nullable=True),
        sa.Column("disk_gb", sa.Integer(), nullable=True),
        sa.Column("bandwidth_gb", sa.Integer(), nullable=True),
        sa.Column("port_mbps", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("line_tags", sa.JSON(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("prev_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("billing_cycle", sa.String(length=20), nullable=False),
        sa.Column("price_options", sa.JSON(), nullable=False),
        sa.Column("purchase_url", sa.String(length=500), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("recommended", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_id", "external_id"),
    )
    op.create_index("ix_products_merchant_id", "products", ["merchant_id"], unique=False)
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_location", "products", ["location"], unique=False)
    op.create_index("ix_products_in_stock", "products", ["in_stock"], unique=False)
    op.create_index("ix_products_recommended", "products", ["recommended"], unique=False)

    op.create_table(
        "stock_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_snapshots_product_id", "stock_snapshots", ["product_id"], unique=False)

    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_snapshots_product_id", "price_snapshots", ["product_id"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("api_token", sa.String(length=64), nullable=False),
        sa.Column("view_mode", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_api_token", "users", ["api_token"], unique=True)

    op.create_table(
        "email_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_codes_email", "email_codes", ["email"], unique=False)

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("notify_restock", sa.Boolean(), nullable=False),
        sa.Column("notify_price_drop", sa.Boolean(), nullable=False),
        sa.Column("min_drop_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id"),
    )
    op.create_index("ix_watchlist_user_id", "watchlist", ["user_id"], unique=False)
    op.create_index("ix_watchlist_product_id", "watchlist", ["product_id"], unique=False)

    op.create_table(
        "notify_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("old_value", sa.String(length=50), nullable=True),
        sa.Column("new_value", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notify_events_product_id", "notify_events", ["product_id"], unique=False)
    op.create_index("ix_notify_events_type", "notify_events", ["type"], unique=False)
    op.create_index("ix_notify_events_created_at", "notify_events", ["created_at"], unique=False)

    op.create_table(
        "notify_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["notify_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notify_logs_user_id", "notify_logs", ["user_id"], unique=False)

    op.create_table(
        "aff_clicks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("src", sa.String(length=32), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("ua", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_aff_clicks_product_id", "aff_clicks", ["product_id"], unique=False)
    op.create_index("ix_aff_clicks_created_at", "aff_clicks", ["created_at"], unique=False)


def downgrade() -> None:
    # baseline 是链条起点：仅允许删表回退到空库
    for name, kinds in [
        ("aff_clicks", ("ix_aff_clicks_created_at", "ix_aff_clicks_product_id")),
        ("notify_logs", ("ix_notify_logs_user_id",)),
        ("notify_events", ("ix_notify_events_created_at", "ix_notify_events_type", "ix_notify_events_product_id")),
        ("watchlist", ("ix_watchlist_product_id", "ix_watchlist_user_id")),
        ("email_codes", ("ix_email_codes_email",)),
        ("users", ("ix_users_api_token", "ix_users_email")),
        ("price_snapshots", ("ix_price_snapshots_product_id",)),
        ("stock_snapshots", ("ix_stock_snapshots_product_id",)),
        (
            "products",
            (
                "ix_products_recommended",
                "ix_products_in_stock",
                "ix_products_location",
                "ix_products_name",
                "ix_products_merchant_id",
            ),
        ),
        ("merchants", ("ix_merchants_slug",)),
    ]:
        for ix in kinds:
            op.drop_index(ix, table_name=name)
        op.drop_table(name)
