"""访问记录上报（PV/UV 统计）。

前端在路由变化时上报一次，落库到 page_views。查询/分析不在本模块提供——
先积累数据，待明确看板需求后再加统计端点。

端点无需认证：访客多数未登录。写入极轻（单条 INSERT），且前端对同一路径
只上报一次，风险可控。
"""

import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_optional_user
from ..models import PageView
from ..services.client_ip import client_ip

router = APIRouter(prefix="/api/track", tags=["track"])

# 详情页 slug 形如「93-20260705-lax-vps-cn2-...」，首段即产品 ID（见 lib/slug）。
# 能解析就记下 product_id，便于统计单个套餐的浏览量；解析不到也不影响 PV 统计。
_SLUG_ID = re.compile(r"^(\d+)-")


class PageViewIn(BaseModel):
    path: str = Field(max_length=255)
    referrer: str | None = Field(default=None, max_length=500)
    # 前端 sessionStorage 生成的会话标识：统计 UV 与跳出率的依据
    session_id: str | None = Field(default=None, max_length=64)


def normalize_route(path: str) -> str:
    """归一化路由：动态段换成占位符，便于按页面聚合 PV。

    /vps/93-2026xxx  → /vps/[slug]   （所有详情页聚合成一个页面）
    /vps?line=cn2    → /vps          （忽略查询串，筛选条件不算独立页面）
    """
    p = path.split("?", 1)[0].rstrip("/") or "/"
    parts = p.split("/")
    if len(parts) >= 3 and parts[1] == "vps" and parts[2]:
        return "/vps/[slug]"
    return p or "/"


def _slug_product_id(route_path: str) -> int | None:
    """从 /vps/{slug} 的 slug 首段解析产品 ID；非详情页或格式不符返回 None。"""
    parts = route_path.split("/")
    if len(parts) < 3 or parts[1] != "vps":
        return None
    m = _SLUG_ID.match(parts[2])
    return int(m.group(1)) if m else None


@router.post("/pageview", status_code=204)
def track_pageview(
    payload: PageViewIn,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_optional_user),
):
    p = payload.path.split("?", 1)[0].rstrip("/") or "/"
    db.add(
        PageView(
            route=normalize_route(payload.path)[:120],
            path=p[:255],
            product_id=_slug_product_id(p),
            user_id=user.id if user else None,
            referrer=(payload.referrer or None),
            ip=client_ip(request),
            ua=(request.headers.get("user-agent", "")[:255] or None),
            session_id=payload.session_id[:64] if payload.session_id else None,
        )
    )
    db.commit()
