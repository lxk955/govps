"""P5 汇率机制测试。外部 API 一律 httpx.MockTransport 模拟——
真实外部链路已单独验证可达（见 refactor-plan §10 P5 行），两者明确区分。

换算方向（全链路统一）：units_per_usd = 兑 1 美元所需该币种单位数，
USD 金额 = 外币金额 ÷ units_per_usd。
含「现实锚点」测试：以真实价值量级断言换算结果，不允许只验证公式自洽。

覆盖：多币种价格、正常更新、每日快照幂等、历史快照匹配、人工覆盖、
断源降级、异常数值/漂移守卫、原始价格不可变、换算价正确且方向正确、
连续断源不伪造历史汇率、新旧表共存迁移验证。
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.models import ExchangeRate, ExchangeRateSnapshot, Merchant, Product
from app.services.rates import (
    convert_historical,
    current_rates_map,
    snapshot_map_for_days,
    update_rates,
)

ERAPI_BODY = {
    "result": "ok",
    "rates": {"CNY": 7.2, "EUR": 0.9, "CAD": 1.35},
}
FRANKFURTER_BODY = {"base": "USD", "rates": {"CNY": 7.25, "EUR": 0.91, "CAD": 1.36}}


def _mock_transport(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_update_rates_normal_writes_rates_and_snapshot(client, db):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "er-api" in str(request.url)  # 主源优先
        return httpx.Response(200, json=ERAPI_BODY)

    result = update_rates(db, client=_mock_transport(handler))
    assert result["ok"] is True
    assert set(result["updated"]) == {"USD", "CNY", "EUR", "CAD"}

    rows = {r.code: r for r in db.scalars(select(ExchangeRate)).all()}
    assert float(rows["CNY"].units_per_usd) == 7.2  # 7.2 元/美元
    assert rows["CNY"].source == "auto"
    assert float(rows["USD"].units_per_usd) == 1.0
    snaps = db.query(ExchangeRateSnapshot).all()
    assert len(snaps) == 4


def test_update_rates_idempotent_same_day(client, db):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ERAPI_BODY)

    update_rates(db, client=_mock_transport(handler))
    first_snap_count = db.query(ExchangeRateSnapshot).count()
    r2 = update_rates(db, client=_mock_transport(handler))
    assert r2["ok"] is True
    assert db.query(ExchangeRateSnapshot).count() == first_snap_count


def test_all_sources_down_keeps_old_values(client, db):
    update_rates(db, client=_mock_transport(lambda req: httpx.Response(200, json=ERAPI_BODY)))
    before = {r.code: (float(r.units_per_usd), r.updated_at) for r in db.scalars(select(ExchangeRate))}

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    result = update_rates(db, client=_mock_transport(down))
    assert result["ok"] is False
    assert "不可用" in result["error"]
    after = {r.code: (float(r.units_per_usd), r.updated_at) for r in db.scalars(select(ExchangeRate))}
    assert after == before  # 断源降级：旧值与 updated_at 完全不动


def test_fallback_source_used_when_primary_down(client, db):
    def handler(request: httpx.Request) -> httpx.Response:
        if "er-api" in str(request.url):
            return httpx.Response(500)
        assert "frankfurter" in str(request.url)
        return httpx.Response(200, json=FRANKFURTER_BODY)

    result = update_rates(db, client=_mock_transport(handler))
    assert result["ok"] is True
    assert float(db.scalar(select(ExchangeRate.units_per_usd).where(ExchangeRate.code == "CNY"))) == 7.25


def test_abnormal_rate_rejected_by_deviation_guard(client, db):
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=ERAPI_BODY)))

    bad = {"result": "ok", "rates": {"CNY": 20.0, "EUR": 0.9, "CAD": 1.35}}
    result = update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=bad)))
    assert result["ok"] is True
    cny = db.scalar(select(ExchangeRate).where(ExchangeRate.code == "CNY"))
    assert float(cny.units_per_usd) == 7.2
    assert any("CNY" in s and "漂移" in s for s in result["skipped"])


def test_manual_override_bypasses_guard_and_marks_manual(client, db):
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=ERAPI_BODY)))
    result = update_rates(db, overrides={"CNY": 20.0})
    assert result["ok"] is True
    assert result["source"] == "manual"
    cny = db.scalar(select(ExchangeRate).where(ExchangeRate.code == "CNY"))
    assert float(cny.units_per_usd) == 20.0
    assert cny.source == "manual"
    snap = db.scalar(
        select(ExchangeRateSnapshot).where(
            ExchangeRateSnapshot.code == "CNY", ExchangeRateSnapshot.date == date.today()
        )
    )
    assert float(snap.units_per_usd) == 20.0
    bad = update_rates(db, overrides={"EUR": -3})
    assert not bad["updated"]
    assert any("EUR" in s for s in bad["skipped"])


# ── 换算方向与契约 ──────────────────────────────────────────────


def _seed_cny_product(db, price: str, ext="cny-1", name="HK Plan") -> Product:
    m = db.scalar(select(Merchant).where(Merchant.slug == "cnyshop"))
    if m is None:
        m = Merchant(slug="cnyshop", name="CNY Shop", website="https://c.example")
        db.add(m)
        db.flush()
    p = Product(
        merchant_id=m.id,
        external_id=ext,
        name=name,
        price=Decimal(price),
        currency="CNY",
        billing_cycle="monthly",
        purchase_url="https://c.example/buy",
        in_stock=True,
    )
    db.add(p)
    db.commit()
    return p


def test_converted_direction_divides_by_units_per_usd(client, db):
    """方向锚定：USD = 外币 ÷ units_per_usd。55 CNY、7.2 元/美元 → ≈$7.64。"""
    p = _seed_cny_product(db, "55")
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=ERAPI_BODY)))

    listed = client.get("/api/products").json()
    item = next(x for x in listed["items"] if x["id"] == p.id)
    assert item["price"] == 55.0 and item["currency"] == "CNY"
    expected = round(55 / 7.2, 2)  # ≈ 7.64，而非乘法得到的 396
    assert item["price_converted"] == pytest.approx(expected)
    assert item["price_yearly_converted"] == pytest.approx(round(660 / 7.2, 2))

    # 数据库原始字段未被回写
    db.expire_all()
    fresh = db.get(Product, p.id)
    assert Decimal(str(fresh.price)) == Decimal("55")
    assert fresh.currency == "CNY"

    detail = client.get(f"/api/products/{p.id}").json()
    assert detail["price_converted"] == pytest.approx(expected)
    assert detail["price"] == 55.0

    # 契约：所有产品恒定返回 converted 字段——USD 产品值恒等于原始美元价
    usd_item = Product(
        merchant_id=fresh.merchant_id, external_id="usd-1", name="US Plan",
        price=Decimal("39.99"), currency="USD", billing_cycle="annually",
        purchase_url="https://c.example/buy", in_stock=True,
    )
    db.add(usd_item)
    db.commit()
    listed2 = client.get("/api/products").json()
    u = next(x for x in listed2["items"] if x["id"] == usd_item.id)
    assert u["price_converted"] == u["price"]
    assert u["price_yearly_converted"] == u["price_yearly"]


def test_reality_anchor_yuan_product_lands_near_100_usd(client, db):
    """现实锚点（禁止只断言公式自洽）：¥673.05 的产品按真实量级汇率
    （约 6.73 元/美元）换算必须落在 $95–105 区间。"""
    p = _seed_cny_product(db, "673.05", ext="anchor", name="Anchor Plan")
    body = {"result": "ok", "rates": {"CNY": 6.7305, "EUR": 0.9, "CAD": 1.35}}
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=body)))

    item = client.get(f"/api/products/{p.id}").json()
    assert 95 <= item["price_converted"] <= 105, (
        f"现实锚点失败：¥673.05 应约 $100，实际 {item['price_converted']}"
    )


def test_converted_fields_null_when_rate_missing(client, db):
    """汇率缺失（未覆盖币种）时 converted 为 null 而非字段缺席；原价不受影响。"""
    m = Merchant(slug="jpyshop", name="JPY Shop", website="https://j.example")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="jpy-1",
        name="JP Plan",
        price=Decimal("1000"),
        currency="JPY",
        billing_cycle="monthly",
        purchase_url="https://j.example/buy",
        in_stock=True,
    )
    db.add(p)
    db.commit()

    listed = client.get("/api/products").json()
    item = next(x for x in listed["items"] if x["id"] == p.id)
    assert "price_converted" in item and "price_yearly_converted" in item
    assert item["price_converted"] is None
    assert item["price_yearly_converted"] is None
    assert item["price"] == 1000.0
    assert item["currency"] == "JPY"


# ── 历史快照 ────────────────────────────────────────────────────


def test_historical_conversion_uses_date_snapshot_not_current(client, db):
    today = date.today()
    yesterday = today - timedelta(days=1)
    for d, units in ((yesterday, 7.0), (today, 8.0)):
        db.add(ExchangeRateSnapshot(code="CNY", date=d, units_per_usd=units))
    db.commit()

    snaps = snapshot_map_for_days(db, days=30)
    current = current_rates_map(db)
    current["CNY"] = 9.99  # 故意污染当前汇率，历史换算不得使用

    assert convert_historical(100, "CNY", yesterday.isoformat(), snaps, current) == pytest.approx(100 / 7.0)
    assert convert_historical(100, "CNY", today.isoformat(), snaps, current) == pytest.approx(100 / 8.0)
    # 快照体系覆盖之前的日期：宁缺毋滥返回 None，绝不退回当前汇率
    gap = today - timedelta(days=5)
    assert convert_historical(100, "CNY", gap.isoformat(), snaps, current) is None
    assert convert_historical(100, "JPY", today.isoformat(), snaps, current) is None


def test_consecutive_update_failures_never_fake_historical_rates(client, db):
    """连续多天汇率源失败：不得用当前汇率冒充历史汇率，
    也不得使用未来日期快照；缺失历史保持不可换算（None）。"""
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=ERAPI_BODY)))

    def down(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    for _ in range(5):
        r = update_rates(db, client=_mock_transport(down))
        assert r["ok"] is False

    today = date.today()
    snaps = snapshot_map_for_days(db, days=30)
    current = current_rates_map(db)
    current["CNY"] = 9.99  # 污染当前汇率

    assert set(snaps.keys()) == {today.isoformat()}  # 失败期间未新增快照
    assert convert_historical(100, "CNY", (today - timedelta(days=1)).isoformat(), snaps, current) is None
    assert convert_historical(100, "CNY", (today - timedelta(days=3)).isoformat(), snaps, current) is None
    # 快照当日正确命中：100 ÷ 7.2
    assert convert_historical(100, "CNY", today.isoformat(), snaps, current) == pytest.approx(100 / 7.2)
    assert convert_historical(100, "CNY", (today - timedelta(days=40)).isoformat(), snaps, current) is None
    snap = db.scalar(
        select(ExchangeRateSnapshot).where(
            ExchangeRateSnapshot.code == "CNY", ExchangeRateSnapshot.date == today
        )
    )
    assert float(snap.units_per_usd) == 7.2


def test_rate_snapshots_endpoint_shape(client, db):
    db.add(ExchangeRate(code="CNY", units_per_usd=7.2))
    db.add(ExchangeRateSnapshot(code="CNY", date=date.today(), units_per_usd=7.2))
    db.commit()
    resp = client.get("/api/rates/snapshots?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert body["base"] == "USD"
    assert body["snapshots"][date.today().isoformat()]["CNY"] == 7.2

    cur = client.get("/api/rates").json()
    assert cur["base"] == "USD"
    cny = next(r for r in cur["rates"] if r["code"] == "CNY")
    assert cny["units_per_usd"] == 7.2


def test_legacy_data_intact_after_new_tables_created(client, db):
    """迁移验证：新增表不破坏既有表结构与数据（向后兼容迁移）。"""
    m = Merchant(slug="legacy", name="Legacy", website="https://l.example")
    db.add(m)
    db.flush()
    db.add(Product(merchant_id=m.id, external_id="old", name="Old Plan",
                   price=Decimal("9.99"), currency="USD",
                   billing_cycle="annually", purchase_url="https://l.example/b"))
    db.commit()
    update_rates(db, client=_mock_transport(lambda r: httpx.Response(200, json=ERAPI_BODY)))

    p = db.scalar(select(Product).where(Product.external_id == "old"))
    assert float(p.price) == 9.99 and p.currency == "USD"
    assert db.query(ExchangeRate).count() == 4
