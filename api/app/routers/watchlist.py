from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..deps import get_current_user
from ..models import PriceSnapshot, Product, User, Watchlist
from ..schemas import WatchIn
from .products import product_to_dict

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def my_watchlist(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    rows = db.scalars(
        select(Watchlist)
        .options(joinedload(Watchlist.product_ref).joinedload(Product.merchant))
        .where(Watchlist.user_id == user.id)
        .order_by(Watchlist.created_at.desc())
    ).all()
    watched_ids = [w.product_id for w in rows]
    mins = (
        dict(
            db.execute(
                select(PriceSnapshot.product_id, func.min(PriceSnapshot.price))
                .where(PriceSnapshot.product_id.in_(watched_ids))
                .group_by(PriceSnapshot.product_id)
            ).all()
        )
        if watched_ids
        else {}
    )
    return [
        {
            "id": w.id,
            "product": product_to_dict(
                w.product_ref,
                snapshot_min=float(mins[w.product_ref.id]) if w.product_ref.id in mins else None,
            ),
            "notify_restock": w.notify_restock,
            "notify_price_drop": w.notify_price_drop,
            "min_drop_percent": float(w.min_drop_percent),
            "created_at": w.created_at.isoformat(),
        }
        for w in rows
    ]


@router.put("/{product_id}", status_code=200)
def watch(
    product_id: int,
    payload: WatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一键关注：不存在则创建，存在则更新通知偏好（幂等）。"""
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="product not found")
    w = db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == user.id, Watchlist.product_id == product_id
        )
    )
    if w is None:
        w = Watchlist(user_id=user.id, product_id=product_id)
        db.add(w)
    w.notify_restock = payload.notify_restock
    w.notify_price_drop = payload.notify_price_drop
    w.min_drop_percent = payload.min_drop_percent
    db.commit()
    return {"ok": True, "watching": True}


@router.get("/{product_id}")
def watch_status(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """单个产品的关注状态与通知偏好（详情页按钮初始化用）。"""
    w = db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == user.id, Watchlist.product_id == product_id
        )
    )
    if w is None:
        return {"watching": False, "notify_restock": True, "notify_price_drop": True,
                "min_drop_percent": 0}
    return {
        "watching": True,
        "notify_restock": w.notify_restock,
        "notify_price_drop": w.notify_price_drop,
        "min_drop_percent": float(w.min_drop_percent),
    }


@router.delete("/{product_id}", status_code=200)
def unwatch(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == user.id, Watchlist.product_id == product_id
        )
    )
    if w is not None:
        db.delete(w)
        db.commit()
    return {"ok": True, "watching": False}
