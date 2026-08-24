from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import EventType, NotifyEvent, Product

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/summary")
def events_summary(
    db: Session = Depends(get_db),
    hours: int = Query(default=24, ge=1, le=720),
):
    """近 N 小时补货/降价事件计数，供首页轻量聚合条展示。"""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    def _count(event_type: str) -> int:
        return db.scalar(
            select(func.count(NotifyEvent.id)).where(
                NotifyEvent.type == event_type, NotifyEvent.created_at >= since
            )
        ) or 0

    return {
        "hours": hours,
        "restock_count": _count(EventType.RESTOCK.value),
        "drop_count": _count(EventType.PRICE_DROP.value),
    }


@router.get("")
def recent_events(
    db: Session = Depends(get_db),
    type: str = Query(default="PRICE_DROP", description="PRICE_DROP / RESTOCK"),
    hours: int = Query(default=24, ge=1, le=720),
    limit: int = Query(default=50, ge=1, le=200),
):
    """最近的价格/库存事件流，供降价榜与补货动态页使用。"""
    if type not in (EventType.PRICE_DROP.value, EventType.RESTOCK.value):
        type = EventType.PRICE_DROP.value
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    rows = db.scalars(
        select(NotifyEvent)
        .options(joinedload(NotifyEvent.product).joinedload(Product.merchant))
        .where(NotifyEvent.type == type, NotifyEvent.created_at >= since)
        .order_by(desc(NotifyEvent.created_at))
        .limit(limit)
    ).all()

    items = []
    for ev in rows:
        p = ev.product
        drop_percent = None
        if ev.type == EventType.PRICE_DROP.value and ev.old_value and ev.new_value:
            old, new = float(ev.old_value), float(ev.new_value)
            if old > 0:
                drop_percent = round((old - new) / old * 100, 1)
        items.append(
            {
                "id": ev.id,
                "type": ev.type,
                "old_value": ev.old_value,
                "new_value": ev.new_value,
                "drop_percent": drop_percent,
                "created_at": ev.created_at.isoformat(),
                "product": {
                    "id": p.id,
                    "name": p.name,
                    "merchant": {"slug": p.merchant.slug, "name": p.merchant.name},
                    "price": float(p.price),
                    "currency": p.currency,
                    "billing_cycle": p.billing_cycle,
                    "in_stock": p.in_stock,
                    "location": p.location,
                    "line_tags": p.line_tags or [],
                },
            }
        )

    # 降价榜按降幅排序，补货动态按时间排序
    if type == EventType.PRICE_DROP.value:
        items.sort(key=lambda x: x["drop_percent"] or 0, reverse=True)

    return {"items": items, "hours": hours, "type": type}
