"""管理后台：运营数据 + 可改配置。仅 ADMIN_EMAILS 中的账号可访问。"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import AffClick, Merchant, PageView, Product, User
from ..services.site_settings import public_settings, upsert_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
            func.count(Product.id).label("products"),
            func.sum(case((Product.in_stock.is_(True), 1), else_=0)).label("in_stock"),
        )
        .outerjoin(Product, Product.merchant_id == Merchant.id)
        .group_by(Merchant.id)
        .order_by(Merchant.name)
    ).all()
    out = []
    for r in rows:
        last = r.last_success_at
        out.append(
            {
                "slug": r.slug,
                "name": r.name,
                "website": r.website,
                "enabled": bool(r.enabled),
                "crawl_interval_minutes": r.crawl_interval_minutes,
                "last_success_at": last.isoformat() if last else None,
                "last_error": r.last_error,
                "products": int(r.products or 0),
                "in_stock": int(r.in_stock or 0),
            }
        )
    return {"merchants": out}


class MerchantPatch(BaseModel):
    enabled: bool | None = None
    crawl_interval_minutes: int | None = None


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
    db.commit()
    return {
        "ok": True,
        "slug": m.slug,
        "enabled": m.enabled,
        "crawl_interval_minutes": m.crawl_interval_minutes,
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
