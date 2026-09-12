"""管理后台：运营数据 + 可改配置。仅站长邮箱（及 ADMIN_EMAILS 附加名单）可访问。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..crawler.registry import CRAWLERS
from ..database import get_db
from ..deps import is_admin_email, require_admin
from ..models import AffClick, CrawlLog, Merchant, NotifyEvent, NotifyLog, PageView, Product, User, Watchlist
from ..services.scan import run_scan
from ..services.site_settings import public_settings, upsert_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

_AFF_PLACEHOLDER = "{url}"


def _aff_code_default(slug: str) -> str | None:
    for c in CRAWLERS:
        if c.slug == slug:
            return getattr(c, "aff_url_template", None)
    return None


def _aff_status(slug: str, template: str | None) -> str:
    if slug == "zgocloud":
        return "unsupported"
    t = (template or "").strip()
    if not t or t == _AFF_PLACEHOLDER:
        return "direct"
    return "active"


def _valid_aff_template(value: str) -> bool:
    t = value.strip()
    if not t or t == _AFF_PLACEHOLDER:
        return True
    if "://" in t.split("{", 1)[0] or t.startswith("{url}") or t.startswith("{pid}"):
        if t.startswith("javascript:") or t.startswith("data:"):
            return False
        if "://" in t and not (t.startswith("https://") or t.startswith("http://")):
            return False
        return True
    return t.startswith("https://") or t.startswith("http://")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _day_start(days_ago: int = 0) -> datetime:
    now = _utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start - timedelta(days=days_ago)


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _distinct_sessions(db: Session, since: datetime, until: datetime | None = None) -> int:
    q = select(func.count(func.distinct(PageView.session_id))).where(
        PageView.created_at >= since,
        PageView.session_id.isnot(None),
        PageView.session_id != "",
    )
    if until is not None:
        q = q.where(PageView.created_at < until)
    return _count(db, q)


def _pv(db: Session, since: datetime, until: datetime | None = None) -> int:
    q = select(func.count()).select_from(PageView).where(PageView.created_at >= since)
    if until is not None:
        q = q.where(PageView.created_at < until)
    return _count(db, q)


def _aff(db: Session, since: datetime, until: datetime | None = None) -> int:
    q = select(func.count()).select_from(AffClick).where(AffClick.created_at >= since)
    if until is not None:
        q = q.where(AffClick.created_at < until)
    return _count(db, q)


def _logged_in_users(db: Session, since: datetime) -> int:
    return _count(
        db,
        select(func.count(func.distinct(PageView.user_id))).where(
            PageView.created_at >= since,
            PageView.user_id.isnot(None),
        ),
    )


@router.get("/overview")
def overview(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    today = _day_start(0)
    d7 = _utcnow() - timedelta(days=7)
    d30 = _utcnow() - timedelta(days=30)

    pages = db.execute(
        select(
            PageView.route,
            func.count().label("pv"),
            func.count(func.distinct(PageView.session_id)).label("uv"),
        )
        .where(PageView.created_at >= d7)
        .group_by(PageView.route)
        .order_by(func.count().desc())
        .limit(12)
    ).all()

    aff_by_merchant = db.execute(
        select(
            Merchant.slug,
            Merchant.name,
            func.count().label("clicks"),
        )
        .select_from(AffClick)
        .join(Product, Product.id == AffClick.product_id)
        .join(Merchant, Merchant.id == Product.merchant_id)
        .where(AffClick.created_at >= d30)
        .group_by(Merchant.slug, Merchant.name)
        .order_by(func.count().desc())
    ).all()

    aff_by_src = db.execute(
        select(AffClick.src, func.count().label("clicks"))
        .where(AffClick.created_at >= d30)
        .group_by(AffClick.src)
        .order_by(func.count().desc())
    ).all()

    # 近 30 天按日
    day_expr = func.strftime("%Y-%m-%d", PageView.created_at)
    pv_daily = {
        r.day: (r.pv, r.uv)
        for r in db.execute(
            select(
                day_expr.label("day"),
                func.count().label("pv"),
                func.count(func.distinct(PageView.session_id)).label("uv"),
            )
            .where(PageView.created_at >= d30)
            .group_by(day_expr)
        ).all()
    }
    aff_day_expr = func.strftime("%Y-%m-%d", AffClick.created_at)
    aff_daily = {
        r.day: r.clicks
        for r in db.execute(
            select(aff_day_expr.label("day"), func.count().label("clicks"))
            .where(AffClick.created_at >= d30)
            .group_by(aff_day_expr)
        ).all()
    }
    daily = []
    for i in range(29, -1, -1):
        day = (_day_start(0) - timedelta(days=i)).date().isoformat()
        pv, uv = pv_daily.get(day, (0, 0))
        daily.append({"date": day, "pv": int(pv), "uv": int(uv), "aff": int(aff_daily.get(day, 0))})

    return {
        "generated_at": _utcnow().isoformat(),
        "visits": {
            "today_pv": _pv(db, today),
            "today_uv": _distinct_sessions(db, today),
            "d7_pv": _pv(db, d7),
            "d7_uv": _distinct_sessions(db, d7),
            "d30_pv": _pv(db, d30),
            "d30_uv": _distinct_sessions(db, d30),
        },
        "users": {
            "total": _count(db, select(func.count()).select_from(User)),
            "today_new": _count(db, select(func.count()).select_from(User).where(User.created_at >= today)),
            "d7_new": _count(db, select(func.count()).select_from(User).where(User.created_at >= d7)),
            "d30_new": _count(db, select(func.count()).select_from(User).where(User.created_at >= d30)),
            "dau": _logged_in_users(db, today),
            "wau": _logged_in_users(db, d7),
            "mau": _logged_in_users(db, d30),
        },
        "activity": {
            "dau": _distinct_sessions(db, today),
            "wau": _distinct_sessions(db, d7),
            "mau": _distinct_sessions(db, d30),
        },
        "aff": {
            "today": _aff(db, today),
            "d7": _aff(db, d7),
            "d30": _aff(db, d30),
            "by_merchant": [
                {"slug": r.slug, "name": r.name, "clicks": int(r.clicks)} for r in aff_by_merchant
            ],
            "by_src": [{"src": r.src, "clicks": int(r.clicks)} for r in aff_by_src],
        },
        "pages": [{"route": r.route, "pv": int(r.pv), "uv": int(r.uv)} for r in pages],
        "daily": daily,
    }


@router.get("/merchants")
def list_merchants(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    rows = db.execute(
        select(
            Merchant.slug,
            Merchant.name,
            Merchant.website,
            Merchant.enabled,
            Merchant.crawl_interval_minutes,
            Merchant.last_success_at,
            Merchant.last_error,
            Merchant.aff_url_template,
            func.count(Product.id).label("products"),
            func.sum(case((Product.in_stock.is_(True), 1), else_=0)).label("in_stock"),
        )
        .outerjoin(Product, Product.merchant_id == Merchant.id)
        .group_by(Merchant.id)
        .order_by(Merchant.name)
    ).all()
    crawler_map = {c.slug: getattr(c, "crawl_method", "官方直连") for c in CRAWLERS}
    d30 = _utcnow() - timedelta(days=30)
    click_rows = db.execute(
        select(Merchant.slug, func.count().label("n"))
        .select_from(AffClick)
        .join(Product, Product.id == AffClick.product_id)
        .join(Merchant, Merchant.id == Product.merchant_id)
        .where(AffClick.created_at >= d30)
        .group_by(Merchant.slug)
    ).all()
    clicks_map = {r.slug: int(r.n) for r in click_rows}
    out = []
    for r in rows:
        last = r.last_success_at
        code_default = _aff_code_default(r.slug)
        template = r.aff_url_template
        out.append(
            {
                "slug": r.slug,
                "name": r.name,
                "website": r.website,
                "enabled": bool(r.enabled),
                "crawl_interval_minutes": r.crawl_interval_minutes,
                "crawl_method": crawler_map.get(r.slug, "官方直连"),
                "last_success_at": last.isoformat() if last else None,
                "last_error": r.last_error,
                "products": int(r.products or 0),
                "in_stock": int(r.in_stock or 0),
                "aff_url_template": template,
                "aff_code_default": code_default,
                "aff_status": _aff_status(r.slug, template),
                "aff_clicks_d30": clicks_map.get(r.slug, 0),
            }
        )
    return {"merchants": out}


class MerchantPatch(BaseModel):
    enabled: bool | None = None
    crawl_interval_minutes: int | None = None
    aff_url_template: str | None = None
    restore_aff_default: bool | None = None


@router.patch("/merchants/{slug}")
def patch_merchant(
    slug: str,
    payload: MerchantPatch,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    m = db.scalar(select(Merchant).where(Merchant.slug == slug))
    if m is None:
        raise HTTPException(status_code=404, detail="merchant not found")
    if payload.enabled is not None:
        m.enabled = payload.enabled
    if payload.crawl_interval_minutes is not None:
        minutes = int(payload.crawl_interval_minutes)
        if minutes < 1:
            minutes = 1
        if minutes > 1440:
            minutes = 1440
        m.crawl_interval_minutes = minutes
    if payload.restore_aff_default:
        m.aff_url_template = _aff_code_default(slug)
    elif payload.aff_url_template is not None:
        raw = payload.aff_url_template.strip()
        if raw and not _valid_aff_template(raw):
            raise HTTPException(status_code=400, detail="invalid aff url template")
        m.aff_url_template = raw or None
    db.commit()
    return {
        "ok": True,
        "slug": m.slug,
        "enabled": m.enabled,
        "crawl_interval_minutes": m.crawl_interval_minutes,
        "aff_url_template": m.aff_url_template,
        "aff_code_default": _aff_code_default(slug),
        "aff_status": _aff_status(slug, m.aff_url_template),
    }


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    return public_settings(db)


class SettingsIn(BaseModel):
    event_dedup_minutes: int | None = None
    daily_mail_cap: int | None = None
    indexnow_enabled: bool | None = None


@router.put("/settings")
def put_settings(
    payload: SettingsIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return upsert_settings(db, payload.model_dump(exclude_unset=True))


@router.get("/crawler/logs")
def get_crawler_logs(
    limit: int = 50,
    slug: str | None = None,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """获取近期爬虫执行历史流水，以及各活跃商家的最新执行快照。"""
    query = select(CrawlLog)
    if slug:
        query = query.where(CrawlLog.merchant_slug == slug)
    query = query.order_by(CrawlLog.created_at.desc()).limit(min(limit, 200))
    logs = db.scalars(query).all()

    # 查询各商家的最新一条记录
    latest_sub = (
        select(
            CrawlLog.merchant_slug,
            func.max(CrawlLog.created_at).label("max_created"),
        )
        .group_by(CrawlLog.merchant_slug)
        .subquery()
    )
    latest_rows = db.scalars(
        select(CrawlLog)
        .join(
            latest_sub,
            (CrawlLog.merchant_slug == latest_sub.c.merchant_slug)
            & (CrawlLog.created_at == latest_sub.c.max_created),
        )
        .order_by(CrawlLog.merchant_name)
    ).all()

    def _fmt(l: CrawlLog):
        return {
            "id": l.id,
            "merchant_id": l.merchant_id,
            "merchant_name": l.merchant_name,
            "merchant_slug": l.merchant_slug,
            "status": l.status,
            "method": l.method,
            "products_count": l.products_count,
            "official_count": l.official_count,
            "in_stock_count": l.in_stock_count,
            "duration_ms": l.duration_ms,
            "message": l.message,
            "error": l.error,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }

    return {
        "logs": [_fmt(l) for l in logs],
        "latest_by_merchant": [_fmt(l) for l in latest_rows],
    }


@router.post("/crawler/scan")
def trigger_crawler_scan(
    force: bool = True,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """管理员在后台手动触发全量爬虫执行与数据入库。"""
    return run_scan(db, force=force)


def _user_row(u: User, *, watch_count: int = 0, last_seen_at=None) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "view_mode": u.view_mode or "card",
        "currency_mode": getattr(u, "currency_mode", None) or "original",
        "is_admin": is_admin_email(u.email),
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "watch_count": int(watch_count or 0),
        "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
    }


@router.get("/users")
def list_users(
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    filt = []
    if q and q.strip():
        filt.append(User.email.ilike(f"%{q.strip()}%"))

    total = _count(db, select(func.count()).select_from(User).where(*filt) if filt else select(func.count()).select_from(User))

    last_seen = (
        select(PageView.user_id, func.max(PageView.created_at).label("last_seen"))
        .where(PageView.user_id.isnot(None))
        .group_by(PageView.user_id)
        .subquery()
    )
    watch_counts = (
        select(Watchlist.user_id, func.count().label("n")).group_by(Watchlist.user_id).subquery()
    )
    stmt = (
        select(User, watch_counts.c.n, last_seen.c.last_seen)
        .outerjoin(watch_counts, watch_counts.c.user_id == User.id)
        .outerjoin(last_seen, last_seen.c.user_id == User.id)
    )
    if filt:
        stmt = stmt.where(*filt)
    rows = db.execute(stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [_user_row(u, watch_count=n or 0, last_seen_at=seen) for u, n, seen in rows],
    }


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")

    watch_n = _count(db, select(func.count()).select_from(Watchlist).where(Watchlist.user_id == u.id))
    last_seen = db.scalar(
        select(func.max(PageView.created_at)).where(PageView.user_id == u.id)
    )
    aff_n = _count(db, select(func.count()).select_from(AffClick).where(AffClick.user_id == u.id))
    pv_n = _count(db, select(func.count()).select_from(PageView).where(PageView.user_id == u.id))

    watches = db.execute(
        select(Watchlist, Product, Merchant)
        .join(Product, Product.id == Watchlist.product_id)
        .join(Merchant, Merchant.id == Product.merchant_id)
        .where(Watchlist.user_id == u.id)
        .order_by(Watchlist.created_at.desc())
    ).all()

    views = db.scalars(
        select(PageView)
        .where(PageView.user_id == u.id)
        .order_by(PageView.created_at.desc())
        .limit(30)
    ).all()

    notifies = db.execute(
        select(NotifyLog, NotifyEvent, Product)
        .join(NotifyEvent, NotifyEvent.id == NotifyLog.event_id)
        .outerjoin(Product, Product.id == NotifyEvent.product_id)
        .where(NotifyLog.user_id == u.id)
        .order_by(NotifyLog.sent_at.desc())
        .limit(30)
    ).all()

    return {
        "user": {
            **_user_row(u, watch_count=watch_n, last_seen_at=last_seen),
            "aff_clicks": aff_n,
            "pageviews": pv_n,
        },
        "watchlist": [
            {
                "product_id": p.id,
                "name": p.name,
                "merchant": m.name,
                "merchant_slug": m.slug,
                "in_stock": bool(p.in_stock),
                "price": float(p.price) if p.price is not None else None,
                "currency": p.currency,
                "notify_restock": bool(w.notify_restock),
                "notify_price_drop": bool(w.notify_price_drop),
                "min_drop_percent": float(w.min_drop_percent or 0),
                "created_at": w.created_at.isoformat() if w.created_at else None,
            }
            for w, p, m in watches
        ],
        "recent_views": [
            {
                "route": v.route,
                "path": v.path,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in views
        ],
        "recent_notifies": [
            {
                "status": log.status,
                "channel": log.channel,
                "event_type": ev.type if ev else None,
                "product_name": p.name if p else None,
                "error": log.error,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
            }
            for log, ev, p in notifies
        ],
    }


