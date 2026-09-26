"""在 user_nodes 表中添加流量周期与统计相关字段。

Revision ID: 0017_traffic_cycle_fields
Revises: 0016_monitor_expire_muted
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_traffic_cycle_fields"
down_revision = "0016_monitor_expire_muted"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}
    
    if "traffic_direction" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "traffic_direction",
                sa.String(10),
                server_default=sa.text("'both'"),
                nullable=False,
            ),
        )

    if "cycle_traffic_rx" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "cycle_traffic_rx",
                sa.BigInteger(),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )

    if "cycle_traffic_tx" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "cycle_traffic_tx",
                sa.BigInteger(),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )

    if "cycle_traffic_reset_at" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "cycle_traffic_reset_at",
                sa.DateTime(timezone=True),
                nullable=True,
            ),
        )

    if "last_reported_rx" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "last_reported_rx",
                sa.BigInteger(),
                nullable=True,
            ),
        )

    if "last_reported_tx" not in node_cols:
        op.add_column(
            "user_nodes",
            sa.Column(
                "last_reported_tx",
                sa.BigInteger(),
                nullable=True,
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    node_cols = {c["name"] for c in inspector.get_columns("user_nodes")}

    cols_to_drop = [
        "traffic_direction",
        "cycle_traffic_rx",
        "cycle_traffic_tx",
        "cycle_traffic_reset_at",
        "last_reported_rx",
        "last_reported_tx",
    ]
    with op.batch_alter_table("user_nodes") as batch_op:
        for col in cols_to_drop:
            if col in node_cols:
                batch_op.drop_column(col)
