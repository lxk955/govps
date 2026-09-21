"""用户 VPS 探针监控表与快照时序表。

Revision ID: 0013_user_nodes_and_snapshots
Revises: 0012_crawl_logs
Create Date: 2026-09-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_user_nodes_and_snapshots"
down_revision = "0012_crawl_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # 1. 扩展 users 表
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_public_enabled" not in user_cols:
        op.add_column(
            "users",
            sa.Column("monitor_public_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        )
    if "monitor_share_token" not in user_cols:
        op.add_column(
            "users",
            sa.Column("monitor_share_token", sa.String(length=64), nullable=True),
        )
        op.create_index("ix_users_monitor_share_token", "users", ["monitor_share_token"], unique=True)

    # 2. 创建 user_nodes 表
    if "user_nodes" not in inspector.get_table_names():
        op.create_table(
            "user_nodes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("country", sa.String(length=10), server_default="hk", nullable=False),
            sa.Column("group_name", sa.String(length=50), server_default="主力", nullable=False),
            sa.Column("tags", sa.JSON(), nullable=False),
            sa.Column("os_type", sa.String(length=30), server_default="debian", nullable=False),
            sa.Column("os_version", sa.String(length=50), nullable=True),
            sa.Column("arch", sa.String(length=20), nullable=True),
            sa.Column("cpu_cores", sa.Integer(), server_default="1", nullable=True),
            sa.Column("price", sa.Numeric(10, 2), nullable=True),
            sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
            sa.Column("billing_cycle", sa.String(length=20), server_default="monthly", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("traffic_limit_gb", sa.Float(), nullable=True),
            sa.Column("is_online", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_demo", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cached_status", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_user_nodes_user_id", "user_nodes", ["user_id"])
        op.create_index("ix_user_nodes_token", "user_nodes", ["token"], unique=True)
        op.create_index("ix_user_nodes_name", "user_nodes", ["name"])
        op.create_index("ix_user_nodes_is_online", "user_nodes", ["is_online"])
        op.create_index("ix_user_nodes_is_demo", "user_nodes", ["is_demo"])
        op.create_index("ix_user_nodes_user_created", "user_nodes", ["user_id", "created_at"])

    # 3. 创建 node_snapshots 表
    if "node_snapshots" not in inspector.get_table_names():
        op.create_table(
            "node_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("node_id", sa.Integer(), sa.ForeignKey("user_nodes.id"), nullable=False),
            sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("cpu_percent", sa.Float(), server_default="0", nullable=False),
            sa.Column("ram_used_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("ram_total_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("swap_used_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("swap_total_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("disk_used_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("disk_total_bytes", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("load_1", sa.Float(), server_default="0", nullable=False),
            sa.Column("load_5", sa.Float(), server_default="0", nullable=False),
            sa.Column("load_15", sa.Float(), server_default="0", nullable=False),
            sa.Column("net_rx_rate", sa.Float(), server_default="0", nullable=False),
            sa.Column("net_tx_rate", sa.Float(), server_default="0", nullable=False),
            sa.Column("net_rx_total", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("net_tx_total", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("uptime_seconds", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("ping_stats", sa.JSON(), nullable=False),
        )
        op.create_index("ix_node_snapshots_node_id", "node_snapshots", ["node_id"])
        op.create_index("ix_node_snapshots_recorded_at", "node_snapshots", ["recorded_at"])
        op.create_index("ix_node_snapshots_node_recorded", "node_snapshots", ["node_id", "recorded_at"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if "node_snapshots" in inspector.get_table_names():
        op.drop_table("node_snapshots")

    if "user_nodes" in inspector.get_table_names():
        op.drop_table("user_nodes")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "monitor_share_token" in user_cols:
        indexes = {idx["name"] for idx in inspector.get_indexes("users")}
        if "ix_users_monitor_share_token" in indexes:
            op.drop_index("ix_users_monitor_share_token", table_name="users")
        op.drop_column("users", "monitor_share_token")
    if "monitor_public_enabled" in user_cols:
        op.drop_column("users", "monitor_public_enabled")
