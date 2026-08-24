"""P1 物化列与列表查询下推的行为测试（refactor-plan §2 #1/#9）。

覆盖：upsert 物化静态字段、扫描期评分物化、聚合键分组语义、
列表端点过滤/排序/聚合语义、merchants 统计口径、/go 直查路径。
"""

from decimal import Decimal

from sqlalchemy import select

from app.crawler.base import RawProduct
from app.models import Merchant, NotifyEvent, Product
from app.routers.products import group_members
from app.services.materialize import refresh_derived_fields
from app.services.scan import upsert_product


def _merchant(db, slug="shopa", name="ShopA") -> Merchant:
    m = Merchant(slug=slug, name=name, website=f"https://{slug}.example")
    db.add(m)
    db.flush()
    return m


def _raw(external_id="sku-1", name="LAX Value 2C2G", **kw) -> RawProduct:
    data = dict(
        external_id=external_id,
        name=name,
        price=Decimal("10.00"),
        currency="USD",
        billing_cycle="annually",
        purchase_url="https://shopa.example/buy",
        in_stock=True,
        location="洛杉矶",
        cpu_cores=2,
        ram_gb=Decimal("2.0"),
        disk_gb=20,
        bandwidth_gb=1000,
        port_mbps=1000,
        line_tags=["CN2 GIA"],
    )
    data.update(kw)
    return RawProduct(**data)


def _product_by_ext(db, external_id: str) -> Product:
    return db.scalar(select(Product).where(Product.external_id == external_id))


def test_upsert_fills_static_fields(db):
    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw())
    db.flush()

    assert p.spec_key
    assert "lax value 2c2g" in p.search_text
    assert p.line_tags_text == "cn2 gia"


def test_spec_key_merges_cycles_splits_product_lines(db):
    m = _merchant(db)
    p1, _ = upsert_product(db, m, _raw(external_id="monthly", billing_cycle="monthly"))
    p2, _ = upsert_product(db, m, _raw(external_id="yearly", billing_cycle="annually"))
    # 不同产品线（同规格不同名称）不得合并
    p3, _ = upsert_product(db, m, _raw(external_id="pro", name="LAX Pro 2C2G"))
    db.flush()

    assert p1.spec_key == p2.spec_key
    assert p3.spec_key != p1.spec_key


def test_refresh_materializes_scores_matches_live_formula(db):
    from app.services.materialize import engagement_snapshot
    from app.services.scoring import calculate_scores_and_reasons

    m = _merchant(db)
    p, _ = upsert_product(db, m, _raw())
    db.flush()
    db.add(NotifyEvent(product_id=p.id, type="RESTOCK", old_value="oos", new_value="in"))
    db.commit()

    refresh_derived_fields(db)
    db.commit()
    db.refresh(p)

    deal_s, pop_s, hot_s, reasons = calculate_scores_and_reasons(
        p, is_recent_restock=True, **{
            k: 0 for k in ("watch_count", "total_clicks", "clicks_7d", "clicks_3h")
        }
    )
    assert (p.deal_score, p.popularity_score, p.hot_score) == (deal_s, pop_s, hot_s)
    assert p.score_reasons == reasons


def test_list_merges_cycles_and_swaps_to_in_stock_rep(client, db):
    m = _merchant(db)
    upsert_product(db, m, _raw(external_id="oos-yearly", billing_cycle="annually",
                               price=Decimal("50.00"), in_stock=False))
    upsert_product(db, m, _raw(external_id="stock-monthly", billing_cycle="monthly",
                               price=Decimal("8.00")))
    db.commit()

    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    # 代表行被有货成员替换：名称/价格/链接来自月付行
    assert item["in_stock"] is True
    assert item["billing_cycle"] == "monthly"
    cycles = {o["billing_cycle"] for o in item["price_options"]}
    assert cycles == {"monthly", "annually"}


def test_list_price_filter_uses_yearly_pushdown(client, db):
    m = _merchant(db)
    upsert_product(db, m, _raw(external_id="cheap", price=Decimal("2.00"), billing_cycle="monthly"))   # 年付 24
    upsert_product(db, m, _raw(external_id="pricey", name="TYO Pro", price=Decimal("90.00")))          # 年付 90
    db.commit()

    body = client.get("/api/products", params={"max_price": 30}).json()
    assert body["total"] == 1
    assert body["items"][0]["price_yearly"] == 24.0


def test_list_line_filter_matches_materialized_text(client, db):
    m = _merchant(db)
    upsert_product(db, m, _raw(external_id="intl", name="SJC Basic", line_tags=["国际线路"],
                               location="圣何塞"))
    db.commit()

    body = client.get("/api/products", params={"line": "international"}).json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "SJC Basic"


def test_merchants_counts_match_card_counts(client, db):
    m = _merchant(db)
    upsert_product(db, m, _raw(external_id="m-monthly", billing_cycle="monthly"))
    upsert_product(db, m, _raw(external_id="m-yearly", billing_cycle="annually"))
    upsert_product(db, m, _raw(external_id="oos", in_stock=False, name="TYO Solo"))
    db.commit()

    merchants = client.get("/api/products/merchants").json()
    mine = next(x for x in merchants if x["slug"] == "shopa")
    assert mine["count"] == 2
    assert mine["in_stock_count"] == 1


def test_group_members_uses_spec_key_lookup(client, db):
    m = _merchant(db)
    upsert_product(db, m, _raw(external_id="g1", billing_cycle="monthly"))
    upsert_product(db, m, _raw(external_id="g2", billing_cycle="annually"))
    upsert_product(db, m, _raw(external_id="other", name="TYO Pro"))
    db.commit()

    target = _product_by_ext(db, "g1")
    members = group_members(db, target)
    assert sorted(p.external_id for p in members) == ["g1", "g2"]
