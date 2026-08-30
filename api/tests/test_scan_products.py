"""Drive shipped upsert_product, is_historical_low, and min_bw filter on SQLite."""

from decimal import Decimal

from sqlalchemy import func, select

from app.crawler.base import RawProduct
from app.models import Merchant, NotifyEvent, PriceSnapshot, Product, StockSnapshot
from app.routers.products import is_historical_low, product_to_dict
from app.services.scan import upsert_product


def _merchant(db) -> Merchant:
    m = Merchant(slug="testshop", name="TestShop", website="https://test.example")
    db.add(m)
    db.flush()
    return m


def _raw(**kwargs) -> RawProduct:
    data = dict(
        external_id="sku-1",
        name="LAX 1C1G",
        price=Decimal("10.00"),
        currency="USD",
        billing_cycle="annually",
        purchase_url="https://test.example/buy",
        in_stock=True,
        location="洛杉矶",
        cpu_cores=1,
        ram_gb=Decimal("1.0"),
        disk_gb=10,
        bandwidth_gb=1000,
        port_mbps=1000,
    )
    data.update(kwargs)
    return RawProduct(**data)


def test_new_in_stock_insert_emits_no_events_and_one_stock_snapshot(db):
    m = _merchant(db)
    p, events = upsert_product(db, m, _raw(in_stock=True, price=Decimal("19.99")))
    db.flush()

    assert events == []
    assert p.in_stock is True
    stocks = db.scalars(select(StockSnapshot).where(StockSnapshot.product_id == p.id)).all()
    assert len(stocks) == 1
    assert stocks[0].in_stock is True
    assert db.scalar(select(func.count(NotifyEvent.id))) == 0


def test_later_oos_to_instock_emits_restock(db):
    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw(in_stock=True))
    db.flush()
    p.in_stock = False
    db.add(StockSnapshot(product_id=p.id, in_stock=False))
    db.flush()

    _, events = upsert_product(db, m, _raw(in_stock=True))
    db.flush()
    assert [e.type for e in events] == ["RESTOCK"]
    assert db.scalar(select(func.count(NotifyEvent.id))) == 1


def test_zero_price_is_not_a_price_drop(db):
    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw(price=Decimal("20.00")))
    db.flush()
    _, events = upsert_product(db, m, _raw(price=Decimal("0")))
    db.flush()
    assert events == []
    db.refresh(p)
    assert Decimal(str(p.price)) == Decimal("20.00")


def test_is_lowest_price_distinct_from_last_step_drop(db):
    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw(price=Decimal("10.00")))
    db.flush()
    upsert_product(db, m, _raw(price=Decimal("5.00")))  # historical min
    db.flush()
    upsert_product(db, m, _raw(price=Decimal("12.00")))
    db.flush()
    p, _events = upsert_product(db, m, _raw(price=Decimal("8.00")))  # drop, but not min
    db.flush()
    db.refresh(p)

    snap_min = db.scalar(
        select(func.min(PriceSnapshot.price)).where(PriceSnapshot.product_id == p.id)
    )
    assert float(snap_min) == 5.0
    assert is_historical_low(p.price, snap_min) is False
    data = product_to_dict(p, snapshot_min=float(snap_min))
    assert data["price_dropped"] is True
    assert data["is_lowest_price"] is False

    p, _ = upsert_product(db, m, _raw(price=Decimal("5.00")))
    db.flush()
    snap_min = db.scalar(
        select(func.min(PriceSnapshot.price)).where(PriceSnapshot.product_id == p.id)
    )
    assert is_historical_low(p.price, snap_min) is True
    data = product_to_dict(p, snapshot_min=float(snap_min))
    assert data["is_lowest_price"] is True


def test_preset_does_not_force_live_sku_oos(db):
    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw(in_stock=True, price=Decimal("10")))
    db.flush()
    upsert_product(
        db,
        m,
        _raw(in_stock=False, price=Decimal("10"), from_preset=True),
    )
    db.flush()
    db.refresh(p)
    assert p.in_stock is True


def test_min_bw_keeps_unmetered(client, db):
    m = _merchant(db)
    metered = Product(
        merchant_id=m.id,
        external_id="m1",
        name="metered",
        price=Decimal("10"),
        purchase_url="https://test.example/a",
        bandwidth_gb=200,
        in_stock=True,
    )
    unmetered = Product(
        merchant_id=m.id,
        external_id="u1",
        name="unmetered",
        price=Decimal("11"),
        purchase_url="https://test.example/b",
        bandwidth_gb=-1,
        in_stock=True,
    )
    db.add_all([metered, unmetered])
    db.commit()

    resp = client.get("/api/products", params={"min_bw": 500})
    assert resp.status_code == 200
    body = resp.json()
    names = {item["name"] for item in body["items"]}
    assert "unmetered" in names
    assert "metered" not in names


def test_product_detail_caps_snapshots_to_recent_window(client, db):
    """详情只回近 90 天、最多 200 个快照，且保持时间正序。"""
    from datetime import datetime, timedelta, timezone

    from app.routers.products import SNAPSHOT_MAX_POINTS

    m = _merchant(db)
    p = Product(
        merchant_id=m.id,
        external_id="hist-1",
        name="hist",
        price=Decimal("10"),
        purchase_url="https://test.example/h",
        in_stock=True,
    )
    db.add(p)
    db.flush()

    now = datetime.now(timezone.utc)
    # 250 个近窗快照 + 1 个 120 天前的旧点（应被窗口滤掉）
    db.add_all(
        [
            PriceSnapshot(
                product_id=p.id,
                price=Decimal(str(i)),
                currency="USD",
                checked_at=now - timedelta(hours=i),
            )
            for i in range(250)
        ]
    )
    db.add(
        PriceSnapshot(
            product_id=p.id,
            price=Decimal("999"),
            currency="USD",
            checked_at=now - timedelta(days=120),
        )
    )
    db.commit()

    detail = client.get(f"/api/products/{p.id}").json()
    snaps = detail["price_snapshots"]
    assert len(snaps) == SNAPSHOT_MAX_POINTS
    times = [s["checked_at"] for s in snaps]
    assert times == sorted(times)
    assert all(s["price"] != 999.0 for s in snaps)
