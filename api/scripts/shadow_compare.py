"""影子比对脚本（refactor-plan §3 P1 / §7）：旧列表实现快照 vs P1 物化实现。

在种子数据上以同参数分别执行：
- _legacy_list_products：改造前 list_products 的逐字逻辑快照（评分实时计算、
  全表内存过滤/聚合/排序）；
- 新实现：经 TestClient 请求 /api/products（SQL 下推 + 物化列读取）。

两者必须产出完全一致的响应（total/items 全字段），任何 diff 即退出码 1。
另比对 /api/products/merchants 新旧统计口径。

用法：api 目录下 .venv/bin/python scripts/shadow_compare.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="shadow-")
os.environ["SKIP_STARTUP_SCAN"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/shadow.sqlite3"
os.environ["TASK_TOKEN"] = "shadow-token"
os.environ["RESEND_API_KEY"] = ""
os.environ["PUBLIC_API_URL"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://testserver"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AffClick,
    Merchant,
    NotifyEvent,
    PriceSnapshot,
    Product,
    Watchlist,
)
from app.routers.products import (  # noqa: E402  （再导出 = 旧实现引用面）
    LINE_FILTERS,
    _get_product_price_options,
    _product_search_text,
    calculate_scores_and_reasons,
    is_historical_low,
    product_to_dict,
    spec_group_key,
)
from app.schemas import yearly_price  # noqa: E402

# ──────────────────────────── 旧实现快照（改造前逐字拷贝，勿改动） ────────────────────────────


def _legacy_line_match(values):
    def match(tags):
        tags = [str(t) for t in (tags or [])]
        joined = " / ".join(tags).lower()
        for v in values:
            if v in LINE_FILTERS:
                includes, excludes = LINE_FILTERS[v]
                if any(inc.lower() in joined for inc in includes) and not any(
                    ex.lower() in joined for ex in excludes
                ):
                    return True
        return False

    return match


def _legacy_list_products(
    db,
    *,
    merchant=None,
    location=None,
    line=None,
    min_price=None,
    max_price=None,
    min_ram=None,
    min_cpu=None,
    min_bw=None,
    min_port=None,
    in_stock=None,
    price_drop=None,
    lowest_price=None,
    recent_restock=None,
    recommended=None,
    keyword=None,
    watched=None,
    user=None,
    sort="hot",
    page=1,
    size=30,
):
    from fastapi import HTTPException
    from sqlalchemy import func, or_, select

    from app.models import Merchant as M

    stmt = (
        select(Product).options(joinedload_merchant()).join(Product.merchant).where(M.enabled.is_(True))
    )
    if merchant:
        stmt = stmt.where(M.slug.in_(merchant))
    if location:
        stmt = stmt.where(or_(*[Product.location.ilike(f"%{loc}%") for loc in location]))
    if min_ram is not None:
        stmt = stmt.where(Product.ram_gb >= min_ram)
    if min_cpu is not None:
        stmt = stmt.where(Product.cpu_cores >= min_cpu)
    if min_bw is not None:
        stmt = stmt.where(or_(Product.bandwidth_gb >= min_bw, Product.bandwidth_gb < 0))
    if min_port is not None:
        stmt = stmt.where(Product.port_mbps >= min_port)
    if in_stock is not None:
        stmt = stmt.where(Product.in_stock == in_stock)
    if price_drop:
        stmt = stmt.where(Product.prev_price.isnot(None), Product.price < Product.prev_price)
    if lowest_price:
        min_price_subq = (
            select(func.min(PriceSnapshot.price)).where(PriceSnapshot.product_id == Product.id).scalar_subquery()
        )
        stmt = stmt.where(Product.prev_price.isnot(None), Product.price <= min_price_subq)
    if recommended:
        stmt = stmt.where(Product.in_stock.is_(True), Product.recommended.is_(True))

    items = [p for p in db.scalars(stmt).unique()]

    if keyword and keyword.strip():
        tokens = [t.strip().lower() for t in keyword.strip().split() if t.strip()]
        if tokens:
            items = [p for p in items if all(t in _product_search_text(p) for t in tokens)]

    def yearly(p):
        return float(yearly_price(p.price, p.billing_cycle))

    if watched:
        if user is None:
            raise HTTPException(status_code=401, detail="login required for watched filter")
        watched_ids = set(db.scalars(select(Watchlist.product_id).where(Watchlist.user_id == user.id)).all())
        items = [p for p in items if p.id in watched_ids]

    if line:
        lm = _legacy_line_match(line)
        items = [p for p in items if lm(p.line_tags)]
    if min_price is not None:
        items = [p for p in items if yearly(p) >= min_price]
    if max_price is not None:
        items = [p for p in items if yearly(p) <= max_price]

    now = datetime.now(timezone.utc)
    t_3h = now - timedelta(hours=3)
    t_7d = now - timedelta(days=7)
    t_48h = now - timedelta(hours=48)

    watch_counts = dict(db.execute(select(Watchlist.product_id, func.count(Watchlist.id)).group_by(Watchlist.product_id)).all())
    clicks_total = dict(db.execute(select(AffClick.product_id, func.count(AffClick.id)).group_by(AffClick.product_id)).all())
    clicks_7d = dict(
        db.execute(select(AffClick.product_id, func.count(AffClick.id)).where(AffClick.created_at >= t_7d).group_by(AffClick.product_id)).all()
    )
    clicks_3h = dict(
        db.execute(select(AffClick.product_id, func.count(AffClick.id)).where(AffClick.created_at >= t_3h).group_by(AffClick.product_id)).all()
    )
    restocked_48h = set(
        db.scalars(select(NotifyEvent.product_id).where(NotifyEvent.type == "RESTOCK", NotifyEvent.created_at >= t_48h)).all()
    )
    dropped_48h = set(
        db.scalars(select(NotifyEvent.product_id).where(NotifyEvent.type == "PRICE_DROP", NotifyEvent.created_at >= t_48h)).all()
    )

    if recent_restock:
        items = [p for p in items if p.id in restocked_48h and p.in_stock]

    def get_scores(p):
        return calculate_scores_and_reasons(
            p,
            watch_count=watch_counts.get(p.id, 0),
            total_clicks=clicks_total.get(p.id, 0),
            clicks_7d=clicks_7d.get(p.id, 0),
            clicks_3h=clicks_3h.get(p.id, 0),
            is_recent_restock=(p.id in restocked_48h),
            is_recent_drop=(p.id in dropped_48h),
        )

    aggregated_items = []
    spec_groups = {}
    for p in items:
        sk = spec_group_key(p)
        d_s, p_s, h_s, rs = get_scores(p)
        if sk in spec_groups:
            entry = aggregated_items[spec_groups[sk]]
            entry[1].extend(_get_product_price_options(p))
            if p.in_stock and not entry[0].in_stock:
                entry[0] = p
            if h_s > entry[2]:
                entry[2] = h_s
                entry[3] = d_s
                entry[4] = p_s
                entry[5] = rs
        else:
            spec_groups[sk] = len(aggregated_items)
            aggregated_items.append([p, list(_get_product_price_options(p)), h_s, d_s, p_s, rs])

    def updated_key(p):
        return p.updated_at or datetime.min.replace(tzinfo=timezone.utc)

    if sort == "deal":
        aggregated_items.sort(key=lambda e: (e[3], updated_key(e[0])), reverse=True)
    elif sort in ("popularity", "popular"):
        aggregated_items.sort(key=lambda e: (e[4], updated_key(e[0])), reverse=True)
    elif sort == "price_asc":
        aggregated_items.sort(key=lambda e: yearly(e[0]))
    elif sort == "price_desc":
        aggregated_items.sort(key=lambda e: yearly(e[0]), reverse=True)
    elif sort == "updated":
        aggregated_items.sort(key=lambda e: updated_key(e[0]), reverse=True)
    else:
        aggregated_items.sort(key=lambda e: (e[2], updated_key(e[0])), reverse=True)

    snapshot_mins = dict(db.execute(select(PriceSnapshot.product_id, func.min(PriceSnapshot.price)).group_by(PriceSnapshot.product_id)).all())

    total = len(aggregated_items)
    start = (page - 1) * size
    paged = aggregated_items[start : start + size]
    return {
        "total": total,
        "items": [
            product_to_dict(
                p,
                _get_product_price_options(p, opts),
                hot_score=h_s,
                deal_score=d_s,
                popularity_score=p_s,
                recommend_reasons=rs,
                is_recent_restock=(p.id in restocked_48h),
                snapshot_min=float(snapshot_mins[p.id]) if p.id in snapshot_mins else None,
            )
            for p, opts, h_s, d_s, p_s, rs in paged
        ],
    }


def joinedload_merchant():
    from sqlalchemy.orm import joinedload

    return joinedload(Product.merchant)


def _legacy_list_merchants(db):
    from sqlalchemy import select

    from app.models import Merchant as M

    merchants = db.scalars(select(M).where(M.enabled.is_(True))).all()
    priority_order = {"bandwagon": 1, "dmit": 2, "vps": 3, "zgocloud": 4, "dedione": 5, "vmiss": 6, "66yun": 7}

    all_products = db.scalars(select(Product)).all()
    spec_groups = {}
    spec_in_stock = {}
    for p in all_products:
        k = spec_group_key(p)
        if k not in spec_groups:
            spec_groups[k] = p.merchant_id
            spec_in_stock[k] = p.in_stock
        else:
            if p.in_stock:
                spec_in_stock[k] = True

    res = []
    for m in merchants:
        pc = sum(1 for _, mid in spec_groups.items() if mid == m.id)
        ic = sum(1 for _, mid in spec_groups.items() if mid == m.id and spec_in_stock.get(_, False))
        res.append(
            {
                "slug": m.slug,
                "name": m.name,
                "website": m.website,
                "count": pc,
                "in_stock_count": ic,
                "last_success_at": m.last_success_at.isoformat() if m.last_success_at else None,
            }
        )
    res.sort(key=lambda x: priority_order.get(x["slug"], 99))
    return res


# ──────────────────────────── 种子数据 ────────────────────────────


def seed(db: SessionLocal):
    Base.metadata.create_all(bind=engine)
    now = datetime.now(timezone.utc)
    ma = Merchant(slug="testa", name="TestA 商家", website="https://a.example", enabled=True)
    mb = Merchant(slug="testb", name="TestB", website="https://b.example", enabled=True)
    mc = Merchant(slug="testc", name="DisabledC", website="https://c.example", enabled=False)
    db.add_all([ma, mb, mc])
    db.flush()

    def prod(m, **kw):
        base = dict(
            merchant_id=m.id,
            currency="USD",
            billing_cycle="annually",
            purchase_url=f"https://{m.slug}.example/buy",
            in_stock=True,
            location="洛杉矶",
            line_tags=["CN2 GIA"],
        )
        base.update(kw)
        p = Product(**base)
        db.add(p)
        return p

    # 同款双周期（月付有货 + 年付缺货）→ 聚合一张卡片且代表为月付行
    prod(ma, external_id="A1", name="LAX Value 2C2G", price=Decimal("10.00"), billing_cycle="monthly",
         cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000)
    prod(ma, external_id="A2", name="LAX Value 2C2G", price=Decimal("50.00"), billing_cycle="annually",
         in_stock=False, cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000)
    # 降价中 + 史低 + 近期补货
    pa3 = prod(ma, external_id="A3", name="TYO Pro 1C1G", price=Decimal("35.99"), prev_price=Decimal("40.00"),
               location="东京", line_tags=["9929"], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15,
               bandwidth_gb=500, port_mbps=500)
    # 半年付下划线周期写法 + 国际线路 + 缺货
    prod(ma, external_id="A4", name="SJC Basic 1C1G", price=Decimal("30.00"), billing_cycle="semi_annually",
         location="圣何塞", line_tags=["国际线路"], in_stock=False, cpu_cores=1, ram_gb=Decimal("1.0"),
         disk_gb=10, bandwidth_gb=-1)
    # 三年付 + 精选推荐
    pb1 = prod(mb, external_id="B1", name="SIN Max 4C8G", price=Decimal("99.00"), billing_cycle="triennially",
               location="新加坡", line_tags=["CMIN2"], recommended=True, cpu_cores=4, ram_gb=Decimal("8.0"),
               disk_gb=100, bandwidth_gb=2000, port_mbps=1000)
    # 关键词命中别名（名称含 7950X）
    prod(mb, external_id="B2", name="FRA 7950X Special", price=Decimal("120.00"),
         location="法兰克福", line_tags=["普通BGP"], cpu_cores=8, ram_gb=Decimal("16.0"), disk_gb=200,
         bandwidth_gb=3000, port_mbps=2500)
    # 停用商家的产品不得出现
    prod(mc, external_id="C1", name="Hidden Product", price=Decimal("5.00"))

    db.flush()
    db.add(PriceSnapshot(product_id=pa3.id, price=Decimal("35.99")))
    db.add(PriceSnapshot(product_id=pa3.id, price=Decimal("42.00")))
    db.add(PriceSnapshot(product_id=pb1.id, price=Decimal("89.00")))

    u = 1
    from app.models import User

    db.add(User(email="u@example.com", api_token="tok-shadow"))
    db.flush()
    from app.models import Watchlist as W

    db.add(W(user_id=u, product_id=db.scalar(select(Product.id).where(Product.external_id == "A1"))))
    for _ in range(3):
        db.add(AffClick(product_id=db.scalar(select(Product.id).where(Product.external_id == "A1")),
                        src="t", created_at=now - timedelta(hours=1)))
    db.add(AffClick(product_id=db.scalar(select(Product.id).where(Product.external_id == "B2")),
                    src="t", created_at=now - timedelta(days=30)))
    db.add(NotifyEvent(product_id=db.scalar(select(Product.id).where(Product.external_id == "A3")),
                       type="RESTOCK", old_value="oos", new_value="in", created_at=now - timedelta(hours=5)))
    db.add(NotifyEvent(product_id=db.scalar(select(Product.id).where(Product.external_id == "A1")),
                       type="PRICE_DROP", old_value="11", new_value="10", created_at=now - timedelta(hours=10)))
    db.commit()


CASES = [
    {},
    {"sort": "deal"},
    {"sort": "popularity"},
    {"sort": "popular"},
    {"sort": "price_asc"},
    {"sort": "price_desc"},
    {"sort": "updated"},
    {"in_stock": True},
    {"in_stock": False},
    {"price_drop": True},
    {"lowest_price": True},
    {"recommended": True},
    {"recent_restock": True},
    {"keyword": "洛杉矶"},
    {"keyword": "lax"},
    {"keyword": "1c 1g"},
    {"keyword": "7950x"},
    {"keyword": "testa 洛杉矶"},
    {"line": ["cn2_gia"]},
    {"line": ["9929"]},
    {"line": ["cn2_gt"]},
    {"line": ["bgp"]},
    {"line": ["international"]},
    {"line": ["cn2_gia", "9929"]},
    {"min_price": 30, "max_price": 60},
    {"min_price": 31.5},
    {"max_price": 36},
    {"min_cpu": 2},
    {"min_ram": 2},
    {"min_bw": 800},
    {"min_port": 800},
    {"merchant": ["testa"]},
    {"merchant": ["testa", "testb"]},
    {"location": ["东京"]},
    {"location": ["los angeles"]},
    {"page": 1, "size": 2},
    {"page": 2, "size": 2},
    {"page": 3, "size": 2},
    {"size": 100},
    {"keyword": "value", "sort": "price_asc", "in_stock": True},
]


def main() -> int:
    from app.services.materialize import refresh_derived_fields

    with SessionLocal() as db:
        seed(db)
        refreshed = refresh_derived_fields(db)
        db.commit()  # TestClient 走独立连接，必须提交后才能读到物化列
        print(f"[seed] products materialized: {refreshed}")

        client = TestClient(__import__("app.main", fromlist=["app"]).app)
        failures = 0
        for i, case in enumerate(CASES):
            new = client.get("/api/products", params=case).json()
            old = _legacy_list_products(db, **case)
            if new != old:
                failures += 1
                print(f"DIFF case#{i} {case}")
                if new.get("total") != old.get("total"):
                    print(f"  total: new={new.get('total')} old={old.get('total')}")
                for j, (ni, oi) in enumerate(zip(new.get("items", []), old.get("items", []))):
                    if ni != oi:
                        for k in ni:
                            if ni.get(k) != oi.get(k):
                                print(f"  item[{j}].{k}: new={ni.get(k)!r} old={oi.get(k)!r}")
                        break
                if len(new.get("items", [])) != len(old.get("items", [])):
                    print(f"  len(items): new={len(new.get('items', []))} old={len(old.get('items', []))}")

        new_m = client.get("/api/products/merchants").json()
        old_m = _legacy_list_merchants(db)
        if new_m != old_m:
            failures += 1
            print("DIFF merchants endpoint")
            print(f"  new={new_m}")
            print(f"  old={old_m}")

        print(f"[result] {len(CASES) + 1} cases, {failures} diffs")
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
