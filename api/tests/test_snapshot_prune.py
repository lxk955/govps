"""快照保留：窗口外的价格/库存点在扫描收尾被删掉。"""

from datetime import datetime, timedelta, timezone

from app.models import Merchant, PageView, PriceSnapshot, Product, StockSnapshot
from app.services.scan import (
    PAGEVIEW_KEEP_DAYS,
    PRICE_SNAPSHOT_KEEP_DAYS,
    STOCK_SNAPSHOT_KEEP_DAYS,
    prune_snapshots,
)


def test_prune_snapshots_keeps_recent_drops_old(db):
    m = Merchant(slug="p", name="P", website="https://p.example")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="1",
        name="Plan",
        price=10,
        purchase_url="https://buy.example",
        in_stock=True,
    )
    db.add(p)
    db.flush()

    now = datetime.now(timezone.utc)
    db.add_all(
        [
            StockSnapshot(product_id=p.id, in_stock=True, checked_at=now - timedelta(days=1)),
            StockSnapshot(
                product_id=p.id,
                in_stock=False,
                checked_at=now - timedelta(days=STOCK_SNAPSHOT_KEEP_DAYS + 5),
            ),
            PriceSnapshot(product_id=p.id, price=9, currency="USD", checked_at=now - timedelta(days=10)),
            PriceSnapshot(
                product_id=p.id,
                price=8,
                currency="USD",
                checked_at=now - timedelta(days=PRICE_SNAPSHOT_KEEP_DAYS + 10),
            ),
            PageView(route="/vps/[slug]", path="/vps/1-plan", created_at=now - timedelta(days=1)),
            PageView(
                route="/vps/[slug]",
                path="/vps/1-plan",
                created_at=now - timedelta(days=PAGEVIEW_KEEP_DAYS + 10),
            ),
        ]
    )
    db.commit()

    result = prune_snapshots(db)
    db.commit()
    assert result["stock"] == 1
    assert result["price"] == 1
    assert result["pageviews"] == 1
    assert db.query(StockSnapshot).count() == 1
    assert db.query(PriceSnapshot).count() == 1
    assert db.query(PageView).count() == 1
    assert float(db.query(PriceSnapshot).one().price) == 9


def test_prune_node_snapshots_keeps_recent(db):
    from app.models import NodeSnapshot, User, UserNode
    from app.services.scan import NODE_SNAPSHOT_KEEP_DAYS

    u = User(email="probe@example.com", api_token="tok-prune")
    db.add(u)
    db.flush()
    node = UserNode(user_id=u.id, token="node_prune", name="n", country="hk")
    db.add(node)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            NodeSnapshot(node_id=node.id, recorded_at=now - timedelta(hours=3), cpu_percent=1),
            NodeSnapshot(
                node_id=node.id,
                recorded_at=now - timedelta(days=NODE_SNAPSHOT_KEEP_DAYS + 1),
                cpu_percent=2,
            ),
        ]
    )
    db.commit()
    result = prune_snapshots(db)
    db.commit()
    assert result["node_snapshots"] == 1
    assert db.query(NodeSnapshot).count() == 1

