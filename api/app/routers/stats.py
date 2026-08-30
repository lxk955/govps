"""访问统计查询（PV / UV / 跳出率）。

只读聚合，不暴露明细——page_views 里有 ip/ua，属站点运营数据，因此本端点
需 task token 鉴权，且只返回聚合值。

用于回答「各页面实际访问量」类问题，例如首页是否只是个跳板：跳出率高说明
用户进来就走，没有进入后续页面。
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import verify_task_token
from ..models import PageView

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _rate(numerator: int, denominator: int) -> float | None:
    """比率。分母为 0 时返回 None 而非 0——「无数据」不应被读成「0% 跳出」。"""
    return round(numerator / denominator, 4) if denominator else None


@router.get("/pageviews")
def pageview_stats(
    days: int = Query(default=7, ge=1, le=180, description="统计最近 N 天"),
    db: Session = Depends(get_db),
    _token: str = Depends(verify_task_token),
):
    """各页面的 PV / UV / 跳出率。

    UV 以 session_id 计（前端 sessionStorage 生成），不用 IP——请求经
    Next.js rewrite 转发后，后端看到的可能只是前端服务的出口 IP。

    跳出率按**入口页**归属：会话首个 pageview 所在的 route 记为该会话入口，
    若该会话全程只浏览了 1 个页面即计为跳出。
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    pv_rows = db.execute(
        select(
            PageView.route,
            func.count().label("pv"),
            func.count(func.distinct(PageView.session_id)).label("uv"),
        )
        .where(PageView.created_at >= since)
        .group_by(PageView.route)
    ).all()

    # 会话内序号（定位入口页）与会话总浏览数（判定是否只看了一页）
    ranked = (
        select(
            PageView.session_id.label("sid"),
            PageView.route.label("route"),
            func.row_number()
            .over(partition_by=PageView.session_id, order_by=(PageView.created_at, PageView.id))
            .label("rn"),
            func.count().over(partition_by=PageView.session_id).label("session_pv"),
        )
        .where(
            PageView.created_at >= since,
            PageView.session_id.isnot(None),
            PageView.session_id != "",
        )
        .subquery()
    )

    bounce_rows = db.execute(
        select(
            ranked.c.route,
            func.sum(case((ranked.c.rn == 1, 1), else_=0)).label("entries"),
            func.sum(
                case((and_(ranked.c.rn == 1, ranked.c.session_pv == 1), 1), else_=0)
            ).label("bounced"),
        ).group_by(ranked.c.route)
    ).all()

    bounce_map = {r.route: (r.entries or 0, r.bounced or 0) for r in bounce_rows}

    pages = []
    for r in pv_rows:
        entries, bounced = bounce_map.get(r.route, (0, 0))
        pages.append(
            {
                "route": r.route,
                "pv": r.pv,
                "uv": r.uv,
                "entries": entries,
                "bounced": bounced,
                "bounce_rate": _rate(bounced, entries),
            }
        )
    pages.sort(key=lambda x: x["pv"], reverse=True)

    total_pv = sum(p["pv"] for p in pages)
    total_entries = sum(p["entries"] for p in pages)
    total_bounced = sum(p["bounced"] for p in pages)
    # 全站 UV 必须跨页面去重，不能把各页 UV 相加（同一访客会看多个页面）
    total_uv = (
        db.scalar(
            select(func.count(func.distinct(PageView.session_id))).where(
                PageView.created_at >= since
            )
        )
        or 0
    )

    return {
        "days": days,
        "since": since.isoformat(),
        "totals": {
            "pv": total_pv,
            "uv": total_uv,
            "entries": total_entries,
            "bounced": total_bounced,
            "bounce_rate": _rate(total_bounced, total_entries),
        },
        "pages": pages,
    }
