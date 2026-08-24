from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ExchangeRate
from ..services.rates import BASE_CODE, snapshot_map_for_days

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("")
def current_rates(db: Session = Depends(get_db)):
    """当前汇率（换算展示的统一口径）：units_per_usd = 兑 1 美元所需该币种单位数。
    USD 金额 = 外币金额 ÷ units_per_usd。"""
    rows = db.scalars(select(ExchangeRate).order_by(ExchangeRate.code)).all()
    return {
        "base": BASE_CODE,
        "rates": [
            {
                "code": r.code,
                "units_per_usd": float(r.units_per_usd),
                "source": r.source,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@router.get("/snapshots")
def rate_snapshots(
    days: int = Query(default=90, ge=1, le=720),
    db: Session = Depends(get_db),
):
    """近 N 天每日快照：{iso_date: {code: units_per_usd}}，历史价格换算按日期匹配使用。"""
    return {
        "base": BASE_CODE,
        "days": days,
        "since": (date.today() - timedelta(days=days)).isoformat(),
        "snapshots": snapshot_map_for_days(db, days),
    }
