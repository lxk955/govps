"""扫描主流程：抓取（按商家分级调度）→ 入库/比对 → 生成事件（去重）→ 入队通知。

单进程顺序执行；邮件发送已异步化（P7）：本流程只写 pending NotifyLog，
由后台 worker 消费，扫描不再被邮件 RTT/失败牵连。
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..crawler.base import RawProduct, make_client, normalize_line_tags, normalize_location
from ..crawler.registry import CRAWLERS
from ..models import (
    EventType,
    ExchangeRateSnapshot,
    Merchant,
    NotifyEvent,
    PriceSnapshot,
    Product,
    StockSnapshot,
)
from .materialize import fill_static_fields, refresh_derived_fields
from .notify import dispatch_event
from .rates import update_rates


def effective_interval_minutes(merchant: Merchant | None, crawler) -> int:
    """抓取间隔兜底链：商家列（运营改库覆盖）→ adapter 默认值 → 全局配置。"""
    if merchant is not None and merchant.crawl_interval_minutes:
        return merchant.crawl_interval_minutes
    default = getattr(crawler, "default_interval_minutes", None)
    if default:
        return default
    return settings.CRAWL_INTERVAL_MINUTES


def ensure_merchants(db: Session) -> None:
    """按爬虫注册表同步商家信息（幂等）。"""
    for crawler in CRAWLERS:
        m = db.scalar(select(Merchant).where(Merchant.slug == crawler.slug))
        if m is None:
            m = Merchant(slug=crawler.slug, name=crawler.name, website=crawler.website)
            db.add(m)
        else:
            m.name = crawler.name
            m.website = crawler.website
        # 代码中配置了返利模板才覆盖，允许在数据库里手动维护
        if crawler.aff_url_template:
            m.aff_url_template = crawler.aff_url_template
        # P7 分级调度：仅填充空值——运营改库设置的间隔不被代码默认值覆盖
        if m.crawl_interval_minutes is None and getattr(crawler, "default_interval_minutes", None):
            m.crawl_interval_minutes = crawler.default_interval_minutes
    db.flush()


def _has_recent_event(db: Session, product_id: int, event_type: str) -> bool:
    """去重：同产品同事件在窗口期内只产生一次。"""
    window = datetime.now(timezone.utc) - timedelta(minutes=settings.EVENT_DEDUP_MINUTES)
    return db.scalar(
        select(NotifyEvent.id).where(
            NotifyEvent.product_id == product_id,
            NotifyEvent.type == event_type,
            NotifyEvent.created_at >= window,
        )
    ) is not None


def _positive_price(price) -> bool:
    try:
        return price is not None and Decimal(str(price)) > 0
    except Exception:
        return False


def _apply_specs(p: Product, raw: RawProduct) -> None:
    """仅在爬虫给出非空值时覆盖规格；空值不再用 `or` 粘住错误的旧数据。"""
    if raw.cpu_cores is not None:
        p.cpu_cores = raw.cpu_cores
    if raw.ram_gb is not None:
        p.ram_gb = raw.ram_gb
    if raw.disk_gb is not None:
        p.disk_gb = raw.disk_gb
    if raw.bandwidth_gb is not None:
        p.bandwidth_gb = raw.bandwidth_gb
    if raw.port_mbps is not None:
        p.port_mbps = raw.port_mbps
    if raw.price_options:
        p.price_options = raw.price_options


def upsert_product(db: Session, merchant: Merchant, raw: RawProduct) -> tuple[Product, list[NotifyEvent]]:
    p = db.scalar(
        select(Product).where(
            Product.merchant_id == merchant.id, Product.external_id == raw.external_id
        )
    )

    incoming_stock = raw.in_stock
    # 预置目录一律缺货：不得把库里仍显示有货的线上 SKU 打成缺货
    if raw.from_preset and p is not None and p.in_stock and not raw.in_stock:
        incoming_stock = p.in_stock

    incoming_price = raw.price if _positive_price(raw.price) else None

    if p is None:
        seed_price = incoming_price if incoming_price is not None else Decimal("0")
        p = Product(
            merchant_id=merchant.id,
            external_id=raw.external_id,
            name=raw.name,
            price=seed_price,
            purchase_url=raw.purchase_url,
            in_stock=incoming_stock,
            currency=raw.currency,
            billing_cycle=raw.billing_cycle,
        )
        db.add(p)
        db.flush()
        if incoming_price is not None:
            db.add(PriceSnapshot(product_id=p.id, price=incoming_price, currency=raw.currency))
        db.add(StockSnapshot(product_id=p.id, in_stock=incoming_stock))
        p.last_checked_at = datetime.now(timezone.utc)
        p.location = normalize_location(raw.location)
        p.line_tags = normalize_line_tags(f"{raw.name} {p.location or ''}", raw.line_tags)
        p.purchase_url = raw.purchase_url or p.purchase_url
        if raw.price_options:
            p.price_options = raw.price_options
        _apply_specs(p, raw)
        if raw.recommended:
            p.recommended = True
        fill_static_fields(p)
        db.flush()
        return p, []

    events: list[NotifyEvent] = []

    # 缺货 → 有货：补货事件（新品已在上面返回，不会走到这里）
    if not p.in_stock and incoming_stock:
        if not _has_recent_event(db, p.id, EventType.RESTOCK.value):
            ev = NotifyEvent(product_id=p.id, type=EventType.RESTOCK.value,
                             old_value="out_of_stock", new_value="in_stock")
            db.add(ev)
            events.append(ev)

    # 降价事件：价格 0 / 解析失败不当作降价
    if (
        incoming_price is not None
        and p.price is not None
        and incoming_price < Decimal(str(p.price))
    ):
        if not _has_recent_event(db, p.id, EventType.PRICE_DROP.value):
            ev = NotifyEvent(product_id=p.id, type=EventType.PRICE_DROP.value,
                             old_value=str(p.price), new_value=str(incoming_price))
            db.add(ev)
            events.append(ev)

    if p.in_stock != incoming_stock:
        db.add(StockSnapshot(product_id=p.id, in_stock=incoming_stock))
    if incoming_price is not None and Decimal(str(p.price)) != incoming_price:
        db.add(PriceSnapshot(product_id=p.id, price=incoming_price, currency=raw.currency))
        p.prev_price = p.price
        p.price = incoming_price

    p.name = raw.name
    p.in_stock = incoming_stock
    p.last_checked_at = datetime.now(timezone.utc)
    if raw.currency:
        p.currency = raw.currency
    if raw.billing_cycle:
        p.billing_cycle = raw.billing_cycle
    p.purchase_url = raw.purchase_url or p.purchase_url
    p.location = normalize_location(raw.location or p.location)
    p.line_tags = normalize_line_tags(f"{p.name} {p.location or ''}", raw.line_tags or p.line_tags)
    _apply_specs(p, raw)
    if raw.recommended:
        p.recommended = True
    # 名称/规格/线路变更后同步物化聚合键与搜索文本（评分由扫描收尾统一刷新）
    fill_static_fields(p)
    db.flush()

    return p, events


def maybe_update_rates(db: Session) -> dict:
    """扫描收尾时的汇率日更：每天只有首次调用真正请求汇率源。

    scan 由 cron 每 5 分钟调用一次，若每次都拉汇率，一天就是近 300 次请求——
    对免费源既不必要也不礼貌。这里以「当日是否已有快照」作闸门：快照表
    unique(code, date)，同日重复写入本就会覆盖同一行，所以当天第二次起的
    调用直接跳过即可。这样运维只需配 scan 这一个 cron，汇率也能保持日更。
    """
    if settings.SKIP_AUTO_RATES:
        return {"skipped": "auto rate fetch disabled"}
    today = datetime.now(timezone.utc).date()
    has_today = db.scalar(
        select(ExchangeRateSnapshot.id).where(ExchangeRateSnapshot.date == today).limit(1)
    )
    if has_today is not None:
        return {"skipped": "today's snapshot already exists"}
    try:
        return update_rates(db)
    except Exception as e:
        # 汇率失败不影响扫描结果本身；下一次扫描会隐式重试
        return {"error": str(e)[:200]}


def run_scan(db: Session, force: bool = False) -> dict:
    """全量扫描入口。P7 分级调度：非 force 时仅抓取「已到期」的商家
    （now - last_success_at ≥ 抓取间隔；从未成功抓取过视为已到期）。
    单个商家失败不影响其他商家（AGENTS.md）。"""
    ensure_merchants(db)
    summary: dict[str, str] = {}
    changed_product_ids: set[int] = set()

    with make_client(settings.SCAN_TIMEOUT) as client:
        now = datetime.now(timezone.utc)
        for crawler in CRAWLERS:
            merchant = db.scalar(select(Merchant).where(Merchant.slug == crawler.slug))
            if merchant is None or not merchant.enabled:
                continue
            if not force:
                interval = effective_interval_minutes(merchant, crawler)
                last = merchant.last_success_at
                if last is not None:
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if now - last < timedelta(minutes=interval):
                        due_in = interval - (now - last).total_seconds() / 60
                        summary[crawler.slug] = (
                            f"skipped (not due, every {interval}min, due in {due_in:.0f}min)"
                        )
                        continue
            try:
                raws = crawler.fetch(client)
            except Exception as e:  # 单个商家失败不影响其他商家
                merchant.last_error = str(e)[:500]
                db.commit()
                summary[crawler.slug] = f"error: {e}"
                continue

            if not raws:
                merchant.last_error = "0 products parsed"
                db.commit()
                summary[crawler.slug] = "0 products (skipped)"
                continue

            merchant.last_success_at = datetime.now(timezone.utc)
            merchant.last_error = None

            official_ids = {raw.external_id for raw in raws if not raw.from_preset}
            event_count = 0
            for raw in raws:
                product, events = upsert_product(db, merchant, raw)
                if events:
                    changed_product_ids.add(product.id)
                for ev in events:
                    db.flush()  # 拿到 ev.id
                    dispatch_event(db, ev, product)
                    event_count += 1

            # 关键：如果在本次有效抓取中消失的存量商品（商家已下架/停售/缺货/过期ID），自动标记为缺货
            # 完整性门槛只看官方实时源：预置目录条数再多也不能当作「抓全了」去把线上 SKU 标缺货
            existing_count = db.scalar(
                select(func.count(Product.id)).where(Product.merchant_id == merchant.id)
            ) or 0
            missing_products: list[Product] = []
            if official_ids and len(official_ids) >= max(3, existing_count * 0.5):
                missing_products = list(
                    db.scalars(
                        select(Product).where(
                            Product.merchant_id == merchant.id,
                            Product.external_id.not_in(official_ids),
                            Product.in_stock.is_(True),
                        )
                    ).all()
                )
                for mp in missing_products:
                    mp.in_stock = False
                    db.add(StockSnapshot(product_id=mp.id, in_stock=False))
            else:
                summary[crawler.slug] = (
                    f"incomplete crawl ({len(official_ids)}/{existing_count} official), missing-mark skipped"
                )

            db.commit()
            if crawler.slug not in summary:
                summary[crawler.slug] = f"{len(raws)} products ({len(missing_products)} marked OOS), {event_count} events"

    # 扫描收尾：按既有公式全量刷新评分/理由等物化列（refactor-plan §2 #1）。
    # 关注数/点击数等时变信号每扫描周期刷新一次，列表请求不再逐条实时计算。
    refreshed = refresh_derived_fields(db)

    # 汇率日更：运维只配 scan 这一个 cron 时，汇率也不会长期过期
    rates = maybe_update_rates(db)
    db.commit()

    # 搜索引擎推送：当有补货或调价事件时，秒级通知 Bing IndexNow
    indexnow_result = None
    if changed_product_ids:
        try:
            from ..crawler.base import slugify
            from .indexnow import submit_to_indexnow

            urls = [f"https://{settings.SITE_DOMAIN}/"]
            for pid in changed_product_ids:
                p = db.get(Product, pid)
                if p:
                    slug = slugify(p.name) or "plan"
                    urls.append(f"https://{settings.SITE_DOMAIN}/vps/{p.id}-{slug}")
            indexnow_result = submit_to_indexnow(urls)
        except Exception as e:
            indexnow_result = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "summary": summary,
        "materialized": refreshed,
        "rates": rates,
        "indexnow": indexnow_result,
    }
