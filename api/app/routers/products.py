from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer, Numeric, and_, case, cast, exists, func, literal, not_, or_, select, String
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_optional_user, verify_task_token
from ..models import (
    AffClick,
    ExchangeRate,
    Merchant,
    NotifyEvent,
    PriceSnapshot,
    Product,
    StockSnapshot,
    User,
    Watchlist,
)
from ..schemas import yearly_price
from ..services.materialize import engagement_snapshot, fill_static_fields, score_product
from ..services.rates import current_rates_map

# P1 自本文件平移至 services/scoring.py 的纯计算函数；此处再导出以保持既有
# 引用面（tests/test_scan_products、scripts/shadow_compare 等）不变。
from ..services.scoring import (  # noqa: F401
    OPTIMIZED_LINES,
    POPULAR_LOCATIONS,
    PREMIUM_LINES,
    _normalize_group_name,
    _product_search_text,
    calculate_scores_and_reasons,
    is_historical_low,
    spec_group_key,
)

router = APIRouter(prefix="/api/products", tags=["products"])

# 支持的排序：hot（综合热度，默认）/ price_asc / price_desc / updated
VALID_SORTS = {"hot", "price_asc", "price_desc", "updated"}

# 线路筛选分类：value -> (需包含的子串列表, 需排除的子串列表)
LINE_FILTERS: dict[str, tuple[list[str], list[str]]] = {
    "cn2_gia": (["CN2 GIA"], []),
    "9929": (["9929"], []),
    "cmin2": (["CMIN2"], []),
    "4837": (["4837"], []),
    "cn2_gt": (["CN2 GT", "CN2"], ["CN2 GIA"]),
    "bgp": (["普通BGP", "BGP"], ["国际线路"]),
    "international": (["国际线路"], []),
}


def _line_tags_sql_expr():
    """线路标签的纯文本表达式（小写），供 LIKE 子串匹配下推。

    使用物化列 line_tags_text（fill_static_fields 维护，空格连接的小写标签），
    而非 CAST(JSON AS TEXT)：SQLite 方言默认 ensure_ascii 序列化会把中文标签
    存成 \\uXXXX 转义，LIKE 原文永远匹配不到。"""
    return func.lower(Product.line_tags_text)


def _line_filter_sql(values: list[str]):
    """线路筛选下推（多选为 OR 匹配），语义与旧实现 `_line_match` 一致。"""
    tags_text = _line_tags_sql_expr()

    def contains(s: str):
        return tags_text.like(f"%{s.lower()}%")

    per_value = []
    for v in values:
        if v not in LINE_FILTERS:
            continue
        includes, excludes = LINE_FILTERS[v]
        cond = or_(*[contains(i) for i in includes])
        if excludes:
            cond = and_(cond, not_(or_(*[contains(e) for e in excludes])))
        per_value.append(cond)
    return or_(*per_value) if per_value else None


def _yearly_price_sql_expr():
    """折算年付价并换算为 USD 的 SQL 表达式（排序、价格区间过滤共用）。

    两步：先按付款周期折算年付价（与 schemas.yearly_price 同款因子），再按汇率
    换算为 USD（USD 金额 = 原币金额 ÷ units_per_usd）。

    换算不可省略：跨币种直接比较原币数值会失真，例如 55（CNY）实际约 8 美元，
    却会被排在 35.88（USD）之后。价格区间过滤同理——min_price/max_price 是美元
    口径，不换算则非 USD 产品几乎不可能落在区间内。

    汇率缺失时 COALESCE 退化为 1，即按原币数值比较：不精确，但不会报错，
    也不会让缺汇率的产品被整体排除（汇率现由启动兜底与扫描日更保证）。

    周期写法先归一化（下划线→连字符）再查表；
    PostgreSQL 中 round(val, 2) 的参数必须为 Numeric 类型。
    """
    cycle = func.replace(func.coalesce(Product.billing_cycle, "annually"), "_", "-")
    factor = case(
        (cycle == "monthly", cast(12.0, Numeric(10, 4))),
        (cycle == "quarterly", cast(4.0, Numeric(10, 4))),
        (cycle == "semi-annually", cast(2.0, Numeric(10, 4))),
        (cycle == "biennially", cast(0.5, Numeric(10, 4))),
        (cycle == "triennially", cast(1.0 / 3.0, Numeric(10, 4))),
        else_=cast(1.0, Numeric(10, 4)),
    )
    # 该币种兑美元汇率（每美元所需原币单位数），USD 恒为 1
    rate = (
        select(ExchangeRate.units_per_usd)
        .where(ExchangeRate.code == Product.currency)
        .scalar_subquery()
    )
    product_price_num = cast(Product.price, Numeric(10, 4))
    yearly = product_price_num * factor
    usd = yearly / func.coalesce(rate, cast(1.0, Numeric(16, 8)))
    return func.round(cast(usd, Numeric(12, 2)), 2)


def _group_key_sql_expr():
    """聚合分组键表达式。物化列缺失的行（如测试直插、未回填旧数据）退化为
    行级唯一键，保证不与其他行误聚合——等价于旧行为「每行独立元组」。

    用 String.concat / ||，不用 func.concat：后者在 SQLite 3.44 之前不存在。
    """
    return func.coalesce(Product.spec_key, literal("u:").concat(cast(Product.id, String)))


def _attach_converted(item: dict, rates: dict[str, float]) -> None:
    """P5：附加 USD 换算价——所有产品恒定返回这两个字段，响应结构不随币种变化：
    - USD 产品：converted 值恒等于原始美元价；
    - 非 USD：USD 金额 = 原价 ÷ units_per_usd（每美元单位数），缺失汇率时置 null。
    只加不改——原始 price/currency 永远保持供应商口径；
    调用方禁止以「字段是否存在」或「是否为 null」推断币种。"""
    cur = item.get("currency")
    if cur == "USD":
        item["price_converted"] = round(item["price"], 2)
        if item.get("price_yearly") is not None:
            item["price_yearly_converted"] = round(item["price_yearly"], 2)
        return
    rate = rates.get(cur) if cur else None
    if not rate or rate <= 0:
        item["price_converted"] = None
        item["price_yearly_converted"] = None
        return
    item["price_converted"] = round(item["price"] / rate, 2)
    if item.get("price_yearly") is not None:
        item["price_yearly_converted"] = round(item["price_yearly"] / rate, 2)


CYCLE_ORDER = {
    "monthly": 1,
    "quarterly": 2,
    "semi_annually": 3,
    "semi-annually": 3,
    "annually": 4,
    "biennially": 5,
    "triennially": 6,
}

# 详情页价格/库存曲线：只回近 90 天、最多 200 个点（时间正序，供折线图）。
# 扫描只在值变化时写快照，200 点通常覆盖数月；超出窗口的点仍留在库里供以后做保留策略。
SNAPSHOT_WINDOW_DAYS = 90
SNAPSHOT_MAX_POINTS = 200


def _get_product_price_options(
    p: Product, extra_options: list[dict] | None = None
) -> list[dict]:
    seen: dict[str, dict] = {}
    base_cycle = (p.billing_cycle or "annually").replace("-", "_")
    seen[base_cycle] = {
        "billing_cycle": base_cycle,
        "price": float(p.price),
        "currency": p.currency or "USD",
        "purchase_url": p.purchase_url,
    }
    for opt in (p.price_options or []) + (extra_options or []):
        if not isinstance(opt, dict):
            continue
        c = (opt.get("billing_cycle") or "").replace("-", "_")
        if not c:
            continue
        pr = float(opt.get("price", 0))
        if c not in seen or pr < seen[c]["price"]:
            seen[c] = {
                "billing_cycle": c,
                "price": pr,
                "currency": opt.get("currency", p.currency or "USD"),
                "purchase_url": opt.get("purchase_url") or p.purchase_url,
            }
    res = list(seen.values())
    res.sort(key=lambda x: CYCLE_ORDER.get(x["billing_cycle"], 99))
    return res


def _recent_snapshots(db: Session, model, product_id: int):
    """详情曲线用：近窗口内最新 N 点，返回时间正序。"""
    since = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_WINDOW_DAYS)
    rows = db.scalars(
        select(model)
        .where(model.product_id == product_id, model.checked_at >= since)
        .order_by(model.checked_at.desc())
        .limit(SNAPSHOT_MAX_POINTS)
    ).all()
    return list(reversed(rows))


def group_members(db: Session, product: Product) -> list[Product]:
    """同一聚合卡片下的全部 SKU（不同付款周期 / pid）。

    P1 起优先走物化聚合键直查（修复 §2 #9：旧实现每次拉取商家全部产品到内存
    再逐条比对）；物化键缺失的行兜底走旧内存路径并顺手补齐。"""
    if product.spec_key is None:
        fill_static_fields(product)
        db.flush()
    if product.spec_key is not None:
        members = db.scalars(
            select(Product)
            .options(joinedload(Product.merchant))
            .where(Product.merchant_id == product.merchant_id, Product.spec_key == product.spec_key)
            .order_by(Product.id.asc())
        ).unique().all()
        if members:
            return members
    siblings = db.scalars(
        select(Product).options(joinedload(Product.merchant)).where(
            Product.merchant_id == product.merchant_id
        )
    ).all()
    key = spec_group_key(product)
    return [s for s in siblings if spec_group_key(s) == key]


def product_to_dict(
    p: Product,
    price_options: list[dict] | None = None,
    hot_score: float | None = None,
    deal_score: float | None = None,
    popularity_score: float | None = None,
    recommend_reasons: list[str] | None = None,
    is_recent_restock: bool = False,
    snapshot_min: float | None = None,
) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "merchant": {"slug": p.merchant.slug, "name": p.merchant.name},
        "cpu_cores": p.cpu_cores,
        "ram_gb": float(p.ram_gb) if p.ram_gb is not None else None,
        "disk_gb": p.disk_gb,
        "bandwidth_gb": p.bandwidth_gb,
        "port_mbps": p.port_mbps,
        "location": p.location,
        "line_tags": p.line_tags or [],
        "price": float(p.price),
        "prev_price": float(p.prev_price) if p.prev_price is not None else None,
        "price_yearly": float(yearly_price(p.price, p.billing_cycle)),
        "price_dropped": p.prev_price is not None and p.price < p.prev_price,
        "is_lowest_price": is_historical_low(p.price, snapshot_min),
        "currency": p.currency,
        "billing_cycle": p.billing_cycle,
        "price_options": price_options or _get_product_price_options(p),
        "purchase_url": p.purchase_url,
        "in_stock": p.in_stock,
        "recommended": p.recommended,
        "hot_score": round(hot_score, 1) if hot_score is not None else None,
        "deal_score": round(deal_score, 1) if deal_score is not None else None,
        "popularity_score": round(popularity_score, 1) if popularity_score is not None else None,
        "recommend_reasons": recommend_reasons or [],
        "is_recent_restock": is_recent_restock,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "last_checked_at": p.last_checked_at.isoformat() if p.last_checked_at else None,
    }


@router.get("")
def list_products(
    db: Session = Depends(get_db),
    merchant: list[str] | None = Query(default=None, description="商家 slug，可多选"),
    location: list[str] | None = Query(default=None, description="机房城市，可多选"),
    line: list[str] | None = Query(
        default=None,
        description="线路分类，可多选：cn2 / cn2_gia / 9929 / cmin2 / 4837 / bgp / international",
    ),
    min_price: float | None = Query(default=None, description="折算年付最低价"),
    max_price: float | None = Query(default=None, description="折算年付最高价"),
    min_ram: float | None = Query(default=None),
    min_cpu: int | None = Query(default=None, description="最小 CPU 核数"),
    min_bw: int | None = Query(default=None, description="最小月流量 GB"),
    min_port: int | None = Query(default=None, description="最小带宽 Mbps"),
    in_stock: bool | None = Query(default=None),
    price_drop: bool | None = Query(default=None, description="只看降价"),
    lowest_price: bool | None = Query(default=None, description="只看史低价"),
    recent_restock: bool | None = Query(default=None, description="只看近48小时补货"),
    recommended: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
    watched: bool | None = Query(default=None, description="只看我关注的产品（需登录）"),
    sort: str = Query(default="hot"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=30, ge=1, le=100),
    user: User | None = Depends(get_optional_user),
):
    """P1 性能改造版（修复 §2 #1）：过滤/分组/排序/分页下推 SQL，
    评分读取扫描期物化列，不再全表加载后逐条实时计算。

    响应形状与聚合语义保持不变：
    - 组内任一成员有货则该组可出现「有货」代表（代表 swap 规则不变）；
    - 展示评分取组内 hot 最高成员的成套值（含理由），规则不变。
    """
    if watched and user is None:
        raise HTTPException(status_code=401, detail="login required for watched filter")

    # ── 过滤条件下推 ──────────────────────────────────────────────
    conds = []
    if merchant:
        conds.append(Merchant.slug.in_(merchant))
    if location:
        conds.append(or_(*[Product.location.ilike(f"%{loc}%") for loc in location]))
    if line:
        cond_line = _line_filter_sql(line)
        if cond_line is not None:
            conds.append(cond_line)
    if min_price is not None:
        conds.append(_yearly_price_sql_expr() >= min_price)
    if max_price is not None:
        conds.append(_yearly_price_sql_expr() <= max_price)
    if min_ram is not None:
        conds.append(Product.ram_gb >= min_ram)
    if min_cpu is not None:
        conds.append(Product.cpu_cores >= min_cpu)
    if min_bw is not None:
        # -1 表示不限流量，应保留在「最低月流量」结果里
        conds.append(or_(Product.bandwidth_gb >= min_bw, Product.bandwidth_gb < 0))
    if min_port is not None:
        conds.append(Product.port_mbps >= min_port)
    if in_stock is not None:
        conds.append(Product.in_stock == in_stock)
    if price_drop:
        conds.append(and_(Product.prev_price.isnot(None), Product.price < Product.prev_price))
    if lowest_price:
        min_price_subq = (
            select(func.min(PriceSnapshot.price))
            .where(PriceSnapshot.product_id == Product.id)
            .scalar_subquery()
        )
        conds.append(and_(Product.prev_price.isnot(None), Product.price <= min_price_subq))
    if recommended:
        conds.append(and_(Product.in_stock.is_(True), Product.recommended.is_(True)))
    if recent_restock:
        t_48h = datetime.now(timezone.utc) - timedelta(hours=48)
        conds.append(
            and_(
                Product.in_stock.is_(True),
                exists(
                    select(NotifyEvent.id).where(
                        NotifyEvent.product_id == Product.id,
                        NotifyEvent.type == "RESTOCK",
                        NotifyEvent.created_at >= t_48h,
                    )
                ),
            )
        )
    if keyword and keyword.strip():
        tokens = [t.strip().lower() for t in keyword.strip().split() if t.strip()]
        if tokens:
            # 物化搜索文本为小写；autoescape 防止 token 中 %/_ 干扰 LIKE
            conds.append(
                and_(*[Product.search_text.contains(t, autoescape=True) for t in tokens])
            )
    if watched:
        conds.append(
            exists(
                select(Watchlist.id).where(
                    Watchlist.product_id == Product.id, Watchlist.user_id == user.id
                )
            )
        )

    gkey = _group_key_sql_expr()
    base = (
        select(Product)
        .options(joinedload(Product.merchant))
        .join(Product.merchant)
        .where(Merchant.enabled.is_(True), *conds)
        .order_by(Product.id.asc())
    )

    # ── 分组分页（SQL 完成）：窗口函数定位组内 hot 最高的展示成员 ──
    rn = (
        func.row_number()
        .over(partition_by=gkey, order_by=(Product.hot_score.desc().nulls_last(), Product.id.asc()))
        .label("rn")
    )
    inner = (
        select(
            gkey.label("gkey"),
            Product.id.label("id"),
            Product.in_stock.label("in_stock"),
            Product.hot_score.label("hot_score"),
            Product.deal_score.label("deal_score"),
            Product.popularity_score.label("popularity_score"),
            rn,
        )
        .join(Product.merchant)
        .where(Merchant.enabled.is_(True), *conds)
        .subquery()
    )
    grouped = (
        select(
            inner.c.gkey.label("gkey"),
            # 代表行 id：有货成员优先（取最小 id），否则全组最小 id —— 与旧实现
            # 「首个成员为代表，遇有货成员替换缺货代表」的迭代语义等价
            func.coalesce(
                func.min(case((inner.c.in_stock.is_(True), inner.c.id))),
                func.min(inner.c.id),
            ).label("rep_id"),
            func.max(inner.c.hot_score).label("g_hot"),
            func.max(case((inner.c.rn == 1, inner.c.deal_score))).label("g_deal"),
            func.max(case((inner.c.rn == 1, inner.c.popularity_score))).label("g_pop"),
            func.min(inner.c.id).label("min_id"),
        )
        .group_by(inner.c.gkey)
        .subquery()
    )
    # 代表行的排序辅助列（相关子查询）
    rep_updated = (
        select(Product.updated_at).where(Product.id == grouped.c.rep_id).scalar_subquery()
    ).label("rep_updated")
    rep_yprice = (
        select(_yearly_price_sql_expr()).where(Product.id == grouped.c.rep_id).scalar_subquery()
    ).label("rep_yprice")

    # 排序（默认综合推荐，同分按代表行更新时间倒序；末位 min_id 复刻旧实现
    # Python 稳定排序的「组首次出现顺序」平局规则）
    if sort == "deal":
        order = (grouped.c.g_deal.desc().nulls_last(), rep_updated.desc(), grouped.c.min_id.asc())
    elif sort in ("popularity", "popular"):
        order = (grouped.c.g_pop.desc().nulls_last(), rep_updated.desc(), grouped.c.min_id.asc())
    elif sort == "price_asc":
        order = (rep_yprice.asc(), grouped.c.min_id.asc())
    elif sort == "price_desc":
        order = (rep_yprice.desc(), grouped.c.min_id.asc())
    elif sort == "updated":
        order = (rep_updated.desc(), grouped.c.min_id.asc())
    else:  # hot / default 综合推荐
        order = (grouped.c.g_hot.desc().nulls_last(), rep_updated.desc(), grouped.c.min_id.asc())

    total = db.scalar(select(func.count(func.distinct(inner.c.gkey))).select_from(inner))
    page_rows = db.execute(
        select(
            grouped.c.gkey,
            grouped.c.rep_id,
            grouped.c.g_hot,
            grouped.c.g_deal,
            grouped.c.g_pop,
            rep_updated,
            rep_yprice,
        )
        .order_by(*order)
        .offset((page - 1) * size)
        .limit(size)
    ).all()
    page_keys = [r.gkey for r in page_rows]

    # ── 仅水合当前页的组成员，按旧规则做代表 swap 与价格选项合并 ──
    aggregated_items: list[list] = []
    if page_keys:
        members = db.scalars(base.where(gkey.in_(page_keys))).unique().all()
        spec_groups: dict[str, int] = {}
        heat_snap: dict | None = None  # 未物化行的兜底快照（懒加载一次）
        for p in members:  # id 升序，等价旧实现的默认迭代顺序
            if (
                p.hot_score is not None
                and p.deal_score is not None
                and p.popularity_score is not None
            ):
                deal_s, pop_s, hot_s = p.deal_score, p.popularity_score, p.hot_score
                reasons = list(p.score_reasons or [])
            else:
                # 兜底：物化列缺失（直插数据/未回填）时按原公式现场计算
                if heat_snap is None:
                    heat_snap = engagement_snapshot(db)
                deal_s, pop_s, hot_s, reasons = calculate_scores_and_reasons(
                    p,
                    watch_count=heat_snap["watch_counts"].get(p.id, 0),
                    total_clicks=heat_snap["clicks_total"].get(p.id, 0),
                    clicks_7d=heat_snap["clicks_7d"].get(p.id, 0),
                    clicks_3h=heat_snap["clicks_3h"].get(p.id, 0),
                    is_recent_restock=(p.id in heat_snap["restocked_48h"]),
                    is_recent_drop=(p.id in heat_snap["dropped_48h"]),
                )

            key = p.spec_key if p.spec_key is not None else f"u:{p.id}"
            if key in spec_groups:
                entry = aggregated_items[spec_groups[key]]
                entry[1].extend(_get_product_price_options(p))
                # 代表产品 swap：有货成员整体替换缺货代表（名称/价格/库存/链接来自同一条记录，
                # 保持卡片信息自洽；不改写 ORM 对象属性，避免脏数据风险）
                if p.in_stock and not entry[0].in_stock:
                    entry[0] = p
                if hot_s > entry[2]:
                    entry[2] = hot_s
                    entry[3] = deal_s
                    entry[4] = pop_s
                    entry[5] = reasons
            else:
                spec_groups[key] = len(aggregated_items)
                aggregated_items.append([p, list(_get_product_price_options(p)), hot_s, deal_s, pop_s, reasons])

        # 关键：水合按 id 升序迭代，输出必须重排回分页查询的排序语义
        aggregated_items = [
            aggregated_items[spec_groups[k]] for k in page_keys if k in spec_groups
        ]

    page_product_ids = [e[0].id for e in aggregated_items]

    # 页内产品的史低价与 48h 补货标记（限定页内 id，避免全表聚合）
    restocked_set: set[int] = set()
    snapshot_mins: dict[int, float] = {}
    if page_product_ids:
        t_48h = datetime.now(timezone.utc) - timedelta(hours=48)
        restocked_set = set(
            db.scalars(
                select(NotifyEvent.product_id).where(
                    NotifyEvent.product_id.in_(page_product_ids),
                    NotifyEvent.type == "RESTOCK",
                    NotifyEvent.created_at >= t_48h,
                )
            ).all()
        )
        snapshot_mins = dict(
            db.execute(
                select(PriceSnapshot.product_id, func.min(PriceSnapshot.price))
                .where(PriceSnapshot.product_id.in_(page_product_ids))
                .group_by(PriceSnapshot.product_id)
            ).all()
        )

    body = {
        "total": total or 0,
        "items": [
            product_to_dict(
                p,
                _get_product_price_options(p, opts),
                hot_score=hot_s,
                deal_score=deal_s,
                popularity_score=pop_s,
                recommend_reasons=reasons,
                is_recent_restock=(p.id in restocked_set),
                snapshot_min=float(snapshot_mins[p.id]) if p.id in snapshot_mins else None,
            )
            for p, opts, hot_s, deal_s, pop_s, reasons in aggregated_items
        ],
    }
    # P5：USD 换算价只加不改（原始 price/currency 保持供应商口径）
    rates = current_rates_map(db)
    for item in body["items"]:
        _attach_converted(item, rates)
    return body


@router.get("/merchants")
def list_merchants(db: Session = Depends(get_db)):
    merchants = db.scalars(select(Merchant).where(Merchant.enabled.is_(True))).all()
    # 按照厂商综合实力、行业资历与口碑自然排序（搬瓦工 > DMIT > V.PS > ZgoCloud > DediOne > VMiss）
    priority_order = {
        "bandwagon": 1,
        "dmit": 2,
        "vps": 3,
        "zgocloud": 4,
        "dedione": 5,
        "vmiss": 6,
        "66yun": 7,
    }

    # 统一按聚合后唯一 SKU 卡片规则统计各商家的套餐款数与在售款数，与前端列表卡片数量严格 1:1 精确对齐
    # P1：分组去重下推 SQL（GROUP BY 商家+聚合键），组内任一成员有货即计在售；
    # 聚合键与列表接口一致（含规范化名称），避免跨产品线合并导致在售数虚高
    gkey = _group_key_sql_expr()
    # 每个分组行 = 一张聚合卡片；组内任一成员有货即计在售
    group_rows = db.execute(
        select(
            Product.merchant_id.label("merchant_id"),
            func.max(cast(Product.in_stock, Integer)).label("any_in_stock"),
        )
        .select_from(Product)
        .group_by(Product.merchant_id, gkey)
    ).all()

    counts: dict[int, int] = {}
    in_stock_counts: dict[int, int] = {}
    for row in group_rows:
        counts[row.merchant_id] = counts.get(row.merchant_id, 0) + 1
        if row.any_in_stock:
            in_stock_counts[row.merchant_id] = in_stock_counts.get(row.merchant_id, 0) + 1

    res = []
    for m in merchants:
        res.append({
            "slug": m.slug,
            "name": m.name,
            "website": m.website,
            "count": counts.get(m.id, 0),
            "in_stock_count": in_stock_counts.get(m.id, 0),
            "last_success_at": m.last_success_at.isoformat() if m.last_success_at else None,
        })
    res.sort(key=lambda x: priority_order.get(x["slug"], 99))
    return res


@router.get("/{product_id}")
def product_detail(product_id: int, db: Session = Depends(get_db)):
    p = db.scalar(
        select(Product).options(joinedload(Product.merchant)).where(Product.id == product_id)
    )
    if p is None or p.merchant is None or not p.merchant.enabled:
        raise HTTPException(status_code=404, detail="product not found")
    extra_opts: list[dict] = []
    for member in group_members(db, p):
        extra_opts.extend(_get_product_price_options(member))
    snap_min = db.scalar(
        select(func.min(PriceSnapshot.price)).where(PriceSnapshot.product_id == p.id)
    )
    t_48h = datetime.now(timezone.utc) - timedelta(hours=48)
    is_recent_restock = db.scalar(
        select(NotifyEvent.id).where(
            NotifyEvent.product_id == p.id,
            NotifyEvent.type == "RESTOCK",
            NotifyEvent.created_at >= t_48h,
        )
    ) is not None
    data = product_to_dict(
        p,
        _get_product_price_options(p, extra_opts),
        # P1 物化的评分与理由在详情页同样展示（缺失则回退实时计算）
        hot_score=p.hot_score,
        deal_score=p.deal_score,
        popularity_score=p.popularity_score,
        recommend_reasons=p.score_reasons or [],
        is_recent_restock=bool(is_recent_restock and p.in_stock),
        snapshot_min=float(snap_min) if snap_min is not None else None,
    )
    if p.hot_score is None:
        snap = engagement_snapshot(db)
        d_s, pop_s, h_s, reasons = calculate_scores_and_reasons(
            p,
            watch_count=snap["watch_counts"].get(p.id, 0),
            total_clicks=snap["clicks_total"].get(p.id, 0),
            clicks_7d=snap["clicks_7d"].get(p.id, 0),
            clicks_3h=snap["clicks_3h"].get(p.id, 0),
            is_recent_restock=(p.id in snap["restocked_48h"]),
            is_recent_drop=(p.id in snap["dropped_48h"]),
        )
        data.update(hot_score=h_s, deal_score=d_s, popularity_score=pop_s, recommend_reasons=reasons)
    data["price_snapshots"] = [
        {"price": float(s.price), "checked_at": s.checked_at.isoformat()}
        for s in _recent_snapshots(db, PriceSnapshot, p.id)
    ]
    data["stock_snapshots"] = [
        {"in_stock": s.in_stock, "checked_at": s.checked_at.isoformat()}
        for s in _recent_snapshots(db, StockSnapshot, p.id)
    ]
    # P5：USD 换算价只加不改
    _attach_converted(data, current_rates_map(db))
    return data


@router.put("/{product_id}/recommend")
def toggle_recommend(
    product_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_task_token),
):
    p = db.scalar(select(Product).where(Product.id == product_id))
    if p is None:
        raise HTTPException(status_code=404, detail="product not found")
    p.recommended = not p.recommended
    db.commit()
    # recommended 参与 Deal Score（+35 与理由）：开关后立即重算该产品的物化评分
    score_product(p, engagement_snapshot(db))
    db.commit()
    return {"ok": True, "recommended": p.recommended}


@router.post("/{product_id}/click")
def track_product_click(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    p = db.scalar(select(Product).where(Product.id == product_id))
    if p is None:
        raise HTTPException(status_code=404, detail="product not found")
    db.add(
        AffClick(
            product_id=p.id,
            src="site_click",
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent", "")[:255],
        )
    )
    db.commit()
    return {"ok": True}

