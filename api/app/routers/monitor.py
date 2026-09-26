"""GoVPS 探针监控路由。

包含：
- 用户 VPS 节点增删改查
- 公开分享链接管理
- 预置真实感演示节点载入与清理
- 节点 24h 历史时序数据查询（Ping 曲线与系统负载）
- VPS Agent 客户端定时数据上报接口
- 一键安装脚本动态分发
"""

import datetime
import math
import random
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.orm import Session, joinedload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, get_optional_user
from ..models import ExchangeRate, NodeSnapshot, User, UserNode, to_iso_utc, utcnow
from ..schemas import (
    MonitorSettingsOut,
    MonitorSettingsUpdate,
    NodeCreate,
    NodeReport,
    NodeUpdate,
    RenewUpdateDateRequest,
    ShareUpdate,
)

router = APIRouter(prefix="/api/monitor", tags=["monitor"])

CURRENT_AGENT_VERSION = "1.2.0"
SNAPSHOT_TTL = timedelta(hours=48)


def _calculate_cost_cny(price: float | None, currency: str, billing_cycle: str, rates: dict[str, float]) -> float:
    """换算为每月 CNY 金额。"""
    if price is None:
        return 0.0
    val = float(price)
    if val <= 0:
        return 0.0

    # 1. 转换为月度均摊
    cycle = (billing_cycle or "monthly").lower()
    if cycle == "monthly":
        monthly_val = val
    elif cycle == "quarterly":
        monthly_val = val / 3.0
    elif cycle == "semi-annually":
        monthly_val = val / 6.0
    elif cycle == "annually":
        monthly_val = val / 12.0
    elif cycle == "biennially":
        monthly_val = val / 24.0
    elif cycle == "triennially":
        monthly_val = val / 36.0
    else:
        monthly_val = val

    # 2. 汇率换算成 USD，再换算成 CNY
    curr = (currency or "USD").upper()
    units_usd = rates.get("USD", 1.0)
    units_cny = rates.get("CNY", 7.2)

    if curr == "CNY":
        return monthly_val
    if curr == "USD":
        return monthly_val * units_cny

    curr_units = rates.get(curr)
    if curr_units and curr_units > 0:
        usd_val = monthly_val / curr_units
        return usd_val * units_cny

    return monthly_val * units_cny


def _node_to_dict(node: UserNode, now: datetime, read_only: bool = False) -> dict:
    """格式化节点详情给前端展示。"""
    status = node.cached_status or {}

    # 判断在线状态：若超过 60 秒未心跳且非演示节点，则判定离线
    is_online = node.is_online
    last_seen = node.last_seen_at
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    if not node.is_demo:
        if not last_seen or (now - last_seen).total_seconds() > 60:
            is_online = False

    # 计算剩余到期天数
    days_left = None
    if node.expires_at:
        exp = node.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        diff = (exp - now).total_seconds() / 86400
        days_left = max(0, int(math.ceil(diff)))

    # 计算在线天数
    uptime_sec = status.get("uptime_seconds", 0)
    uptime_days = uptime_sec // 86400

    # 流量配额
    quota_gb = node.traffic_limit_gb
    rx_bytes = status.get("net_rx_total", 0)
    tx_bytes = status.get("net_tx_total", 0)
    total_used_bytes = rx_bytes + tx_bytes

    remaining_gb = None
    if quota_gb and quota_gb > 0:
        quota_bytes = quota_gb * (1024 ** 3)
        remaining_gb = max(0.0, round((quota_bytes - total_used_bytes) / (1024 ** 3), 1))

    # 内核版本提取（兼容旧探针将内核存入 os_version 的情况）
    kernel_ver = status.get("kernel_version")
    if not kernel_ver and node.os_type == "linux" and node.os_version and ("-" in node.os_version or node.os_version.count(".") >= 2):
        kernel_ver = node.os_version

    return {
        "id": node.id,
        "token": None if read_only else node.token,
        "name": node.name,
        "country": (node.country or "hk").lower(),
        "group_name": node.group_name or "主力",
        "tags": node.tags or [],
        "os_type": (node.os_type or "debian").lower(),
        "os_version": node.os_version,
        "arch": node.arch,
        "cpu_cores": node.cpu_cores or 1,
        "price": float(node.price) if node.price is not None else None,
        "currency": node.currency or "USD",
        "billing_cycle": node.billing_cycle or "monthly",
        "expires_at": to_iso_utc(node.expires_at),
        "days_left": days_left,
        "expire_notify_enabled": node.expire_notify_enabled,
        "expire_notify_stages": node.expire_notify_stages,
        "notified_expire_stages": node.notified_expire_stages or [],
        "expire_muted": bool(getattr(node, "expire_muted", False)),
        "traffic_limit_gb": node.traffic_limit_gb,
        "remaining_gb": remaining_gb,
        "is_online": is_online,
        "is_demo": node.is_demo,
        "is_public": bool(node.is_public) if getattr(node, "is_public", None) is not None else True,
        "uptime_days": uptime_days,
        "last_seen_at": to_iso_utc(node.last_seen_at),
        "created_at": to_iso_utc(node.created_at),
        # 实时指标
        "metrics": {
            "uptime_days": uptime_days,
            "kernel_version": kernel_ver,
            "agent_version": status.get("agent_version"),
            "auto_update": status.get("auto_update", True),
            "cpu_percent": round(float(status.get("cpu_percent") if status.get("cpu_percent") is not None else 0.0), 2),
            "ram_used_bytes": int(status.get("ram_used_bytes") or 0),
            "ram_total_bytes": int(status.get("ram_total_bytes") or 0),
            "swap_used_bytes": int(status.get("swap_used_bytes") or 0),
            "swap_total_bytes": int(status.get("swap_total_bytes") or 0),
            "disk_used_bytes": int(status.get("disk_used_bytes") or 0),
            "disk_total_bytes": int(status.get("disk_total_bytes") or 0),
            "load_1": round(float(status.get("load_1") if status.get("load_1") is not None else 0.0), 2),
            "load_5": round(float(status.get("load_5") if status.get("load_5") is not None else 0.0), 2),
            "load_15": round(float(status.get("load_15") if status.get("load_15") is not None else 0.0), 2),
            "net_rx_rate": round(float(status.get("net_rx_rate") if status.get("net_rx_rate") is not None else 0.0), 2),
            "net_tx_rate": round(float(status.get("net_tx_rate") if status.get("net_tx_rate") is not None else 0.0), 2),
            "net_rx_total": rx_bytes,
            "net_tx_total": tx_bytes,
            "uptime_seconds": uptime_sec,
            "ping_stats": status.get("ping_stats") or [],
            "ping_history": status.get("ping_history") or [],  # 最近 30 次测速色带样本
        },
    }


@router.get("/nodes")
def get_nodes(
    share: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """获取节点监控面板数据（支持登录自用与只读公开分享）。"""
    read_only = False
    target_user: User | None = None

    if share:
        target_user = db.scalar(
            select(User).where(User.monitor_share_token == share, User.monitor_public_enabled == True)
        )
        if not target_user:
            raise HTTPException(status_code=404, detail="公开监控主页未开启或链接已失效")
        read_only = True
    else:
        if not user:
            raise HTTPException(status_code=401, detail="请先登录后访问探针面板")
        target_user = user

    now = utcnow()
    stmt = select(UserNode).where(UserNode.user_id == target_user.id)
    if read_only:
        stmt = stmt.where(UserNode.is_public == True)
    nodes = db.scalars(stmt.order_by(UserNode.created_at.asc())).all()

    # 拉取当前汇率做资产金额折算
    rates_rows = db.scalars(select(ExchangeRate)).all()
    rates = {r.code: float(r.units_per_usd) for r in rates_rows}
    if "USD" not in rates:
        rates["USD"] = 1.0
    if "CNY" not in rates:
        rates["CNY"] = 7.2

    node_list = []
    total_rx_rate = 0.0
    total_tx_rate = 0.0
    total_rx_bytes = 0
    total_tx_bytes = 0
    total_cost_cny = 0.0
    groups_map: dict[str, int] = {}
    countries_map: dict[str, int] = {}

    for n in nodes:
        d = _node_to_dict(n, now, read_only=read_only)
        node_list.append(d)

        # 统计
        m = d["metrics"]
        if d["is_online"]:
            total_rx_rate += m["net_rx_rate"]
            total_tx_rate += m["net_tx_rate"]
        total_rx_bytes += m["net_rx_total"]
        total_tx_bytes += m["net_tx_total"]

        cost = _calculate_cost_cny(n.price, n.currency, n.billing_cycle, rates)
        total_cost_cny += cost

        grp = d["group_name"]
        groups_map[grp] = groups_map.get(grp, 0) + 1

        ctry = d["country"]
        countries_map[ctry] = countries_map.get(ctry, 0) + 1

    online_count = sum(1 for n in node_list if n["is_online"])
    total_count = len(node_list)
    online_segments = [bool(n["is_online"]) for n in node_list]

    summary = {
        "online_count": online_count,
        "total_count": total_count,
        "online_segments": online_segments,
        "bandwidth": {
            "rx_rate": total_rx_rate,
            "tx_rate": total_tx_rate,
            "total_rate": total_rx_rate + total_tx_rate,
        },
        "traffic": {
            "rx_total": total_rx_bytes,
            "tx_total": total_tx_bytes,
            "total": total_rx_bytes + total_tx_bytes,
        },
        "asset": {
            "total_cost_cny": round(total_cost_cny, 2),
            "currency": "CNY",
        },
        "groups": [{"name": k, "count": v} for k, v in groups_map.items()],
        "countries": [{"code": k, "count": v} for k, v in countries_map.items()],
    }

    return {
        "nodes": node_list,
        "summary": summary,
        "user_info": {
            "email": None if read_only else target_user.email,
            "is_owner": not read_only,
            "public_enabled": target_user.monitor_public_enabled if not read_only else True,
            "share_token": None if read_only else target_user.monitor_share_token,
        },
    }


@router.post("/nodes")
def create_node(
    payload: NodeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """添加 VPS 监控节点。"""
    token = f"node_{secrets.token_urlsafe(32)}"
    node = UserNode(
        user_id=user.id,
        token=token,
        name=payload.name,
        country=payload.country.lower(),
        group_name=payload.group_name or "主力",
        tags=payload.tags or [],
        os_type=(payload.os_type or "linux").lower(),
        cpu_cores=payload.cpu_cores or 1,
        price=payload.price,
        currency=payload.currency or "USD",
        billing_cycle=payload.billing_cycle or "monthly",
        expires_at=payload.expires_at,
        expire_notify_enabled=payload.expire_notify_enabled,
        expire_notify_stages=payload.expire_notify_stages,
        notified_expire_stages=[],
        traffic_limit_gb=payload.traffic_limit_gb,
        is_online=False,
        is_demo=False,
        is_public=payload.is_public if payload.is_public is not None else False,
        cached_status={
            "cpu_percent": 0.0,
            "ram_used_bytes": 0,
            "ram_total_bytes": 0,
            "disk_used_bytes": 0,
            "disk_total_bytes": 0,
            "load_1": 0.0,
            "load_5": 0.0,
            "load_15": 0.0,
            "net_rx_rate": 0.0,
            "net_tx_rate": 0.0,
            "net_rx_total": 0,
            "net_tx_total": 0,
            "uptime_seconds": 0,
            "ping_stats": [],
            "ping_history": [],
        },
    )
    db.add(node)
    db.commit()
    db.refresh(node)

    api_origin = settings.PUBLIC_API_URL or "https://govps.xyz"
    install_command = f"curl -fsSL {api_origin}/api/monitor/agent.sh | sudo bash -s -- --token {token} --url {api_origin}"

    return {
        "node": _node_to_dict(node, utcnow()),
        "install_command": install_command,
        "token": token,
    }


@router.put("/nodes/{node_id}")
def update_node(
    node_id: int,
    payload: NodeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新节点资产与属性配置。"""
    node = db.get(UserNode, node_id)
    if not node or node.user_id != user.id:
        raise HTTPException(status_code=404, detail="节点不存在")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        node.name = data["name"]
    if "country" in data and data["country"] is not None:
        node.country = data["country"].lower()
    if "group_name" in data:
        node.group_name = data["group_name"]
    if "tags" in data:
        node.tags = data["tags"]
    if "os_type" in data and data["os_type"] is not None:
        node.os_type = data["os_type"].lower()
    if "cpu_cores" in data:
        node.cpu_cores = data["cpu_cores"]
    if "price" in data:
        node.price = data["price"]
    if "currency" in data:
        node.currency = data["currency"]
    if "billing_cycle" in data:
        node.billing_cycle = data["billing_cycle"]
    if "expires_at" in data:
        if node.expires_at != data["expires_at"]:
            # 到期日更新时重置已通知阶段与静音标记，进入下一轮提醒周期
            node.notified_expire_stages = []
            node.expire_muted = False
        node.expires_at = data["expires_at"]
    if "expire_muted" in data and data["expire_muted"] is not None:
        node.expire_muted = bool(data["expire_muted"])
    if "expire_notify_enabled" in data:
        node.expire_notify_enabled = data["expire_notify_enabled"]
    if "expire_notify_stages" in data:
        node.expire_notify_stages = data["expire_notify_stages"]
    if "traffic_limit_gb" in data:
        node.traffic_limit_gb = data["traffic_limit_gb"]
    if "is_public" in data:
        node.is_public = data["is_public"]

    db.commit()
    db.refresh(node)
    return {"node": _node_to_dict(node, utcnow())}


@router.delete("/nodes/{node_id}")
def delete_node(
    node_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除节点及关联的所有快照。"""
    node = db.get(UserNode, node_id)
    if not node or node.user_id != user.id:
        raise HTTPException(status_code=404, detail="节点不存在")

    db.execute(delete(NodeSnapshot).where(NodeSnapshot.node_id == node.id))
    db.delete(node)
    db.commit()
    return {"ok": True}


@router.post("/share")
def toggle_share(
    payload: ShareUpdate | None = None,
    enabled: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """开启或关闭公开监控分享页面，并支持设置公开展示的节点。"""
    target_enabled = True
    if payload is not None and payload.enabled is not None:
        target_enabled = payload.enabled
    elif enabled is not None:
        target_enabled = enabled

    if not user.monitor_share_token:
        user.monitor_share_token = secrets.token_urlsafe(16)
    user.monitor_public_enabled = target_enabled

    if payload and payload.public_node_ids is not None:
        target_ids = set(payload.public_node_ids)
        user_nodes = db.scalars(select(UserNode).where(UserNode.user_id == user.id)).all()
        for un in user_nodes:
            un.is_public = un.id in target_ids

    db.commit()
    return {
        "public_enabled": user.monitor_public_enabled,
        "share_token": user.monitor_share_token,
    }


@router.get("/settings", response_model=MonitorSettingsOut)
def get_monitor_settings(
    user: User = Depends(get_current_user),
):
    """获取当前用户的探针全局提醒配置及通知渠道。"""
    stages = user.monitor_expire_stages or [15, 7, 3, 1]
    return {
        "expire_notify_enabled": user.monitor_expire_notify_enabled,
        "expire_notify_stages": stages,
        "email": user.email,
        "channels": [
            {
                "id": "email",
                "name": "电子邮箱 (Resend)",
                "target": user.email,
                "enabled": True,
                "status": "active",
                "is_primary": True,
            },
            {
                "id": "webhook",
                "name": "Custom Webhook",
                "target": None,
                "enabled": False,
                "status": "coming_soon",
                "is_primary": False,
            },
            {
                "id": "telegram",
                "name": "Telegram Bot",
                "target": None,
                "enabled": False,
                "status": "coming_soon",
                "is_primary": False,
            },
        ],
    }


@router.put("/settings", response_model=MonitorSettingsOut)
def update_monitor_settings(
    payload: MonitorSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新当前用户的探针全局提醒配置。"""
    if payload.expire_notify_enabled is not None:
        user.monitor_expire_notify_enabled = payload.expire_notify_enabled
    if payload.expire_notify_stages is not None:
        user.monitor_expire_stages = sorted(
            [int(s) for s in payload.expire_notify_stages if int(s) >= 0], reverse=True
        )

    db.commit()
    db.refresh(user)
    return get_monitor_settings(user=user)


@router.post("/notify/test")
def test_expire_notification(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """向当前登录用户的邮箱发送一封测试到期提醒邮件，验证通知连通性。"""
    from ..services.notifications.expiration_checker import send_test_expiration_email

    ok, err = send_test_expiration_email(db, user)
    if not ok:
        raise HTTPException(status_code=400, detail=f"测试邮件发送失败: {err}")
    return {"ok": True, "message": f"测试邮件已成功发送至 {user.email}"}


def _calculate_next_expiry(exp: datetime, billing_cycle: str | None) -> str:
    import calendar

    cycle = (billing_cycle or "monthly").lower()
    month_offsets = {
        "monthly": 1,
        "quarterly": 3,
        "semi-annually": 6,
        "semi_annually": 6,
        "annually": 12,
        "biennially": 24,
        "triennially": 36,
    }
    months = month_offsets.get(cycle, 1)
    new_year = exp.year + (exp.month + months - 1) // 12
    new_month = (exp.month + months - 1) % 12 + 1
    max_days = calendar.monthrange(new_year, new_month)[1]
    new_day = min(exp.day, max_days)
    next_dt = exp.replace(year=new_year, month=new_month, day=new_day)
    return next_dt.strftime("%Y-%m-%d")


@router.get("/renew-action")
def get_renew_action_node(
    token: str = Query(..., description="安全续费 Action Token"),
    db: Session = Depends(get_db),
):
    """免登录查看续费节点详情并自动执行本周期静音。若节点已更新过到期日，旧链接不会误静音新周期。"""
    from ..services.notifications.expiration_checker import verify_renewal_token

    payload, node = verify_renewal_token(token, db=db)
    if not payload or not node:
        raise HTTPException(status_code=400, detail="续费操作链接无效或已过期，请重新登录探针面板操作。")

    if node.user_id != payload.get("uid"):
        raise HTTPException(status_code=404, detail="未找到对应的探针节点。")

    node_current_exp = to_iso_utc(node.expires_at) or ""
    token_cycle_exp = payload.get("nexp") or ""
    # 判断当前链接是否属于已过期的旧周期（即用户已经更新过该节点的到期日）
    is_stale_cycle = bool(node_current_exp and token_cycle_exp and token_cycle_exp != node_current_exp)

    # 仅当 token 属于当前未续费周期时才执行静音；若节点已被更新，绝对不能误将新周期静音！
    if not is_stale_cycle:
        if not node.expire_muted:
            node.expire_muted = True
            db.commit()
            db.refresh(node)

    suggested_next = None
    if node.expires_at:
        suggested_next = _calculate_next_expiry(node.expires_at, node.billing_cycle)

    return {
        "id": node.id,
        "name": node.name,
        "country": (node.country or "hk").lower(),
        "group_name": node.group_name or "主力",
        "billing_cycle": node.billing_cycle or "monthly",
        "price": float(node.price) if node.price is not None else None,
        "currency": node.currency or "USD",
        "current_expires_at": to_iso_utc(node.expires_at),
        "suggested_next_expires_at": suggested_next,
        "is_muted": bool(node.expire_muted),
        "cycle_stale": is_stale_cycle,
        "token_cycle_expires_at": token_cycle_exp,
    }


@router.post("/renew-action/unmute")
def unmute_renew_action(
    token: str = Query(..., description="安全续费 Action Token"),
    db: Session = Depends(get_db),
):
    """撤销静音：恢复本周期的到期阶段提醒。"""
    from ..services.notifications.expiration_checker import verify_renewal_token

    payload, node = verify_renewal_token(token, db=db)
    if not payload or not node:
        raise HTTPException(status_code=400, detail="操作链接无效或已过期。")

    if node.user_id != payload.get("uid"):
        raise HTTPException(status_code=404, detail="未找到对应的探针节点。")

    node_current_exp = to_iso_utc(node.expires_at) or ""
    token_cycle_exp = payload.get("nexp") or ""
    if node_current_exp and token_cycle_exp and token_cycle_exp != node_current_exp:
        raise HTTPException(status_code=400, detail="该节点已更新为新周期到期日，旧周期的链接已失效。")

    node.expire_muted = False
    db.commit()
    return {"ok": True, "is_muted": False}


@router.post("/renew-action/update-date")
def update_date_renew_action(
    body: RenewUpdateDateRequest,
    token: str = Query(..., description="安全续费 Action Token"),
    db: Session = Depends(get_db),
):
    """通过 Action Token 快速更新下次到期日，自动解除静音并开启新周期。"""
    from ..services.notifications.expiration_checker import verify_renewal_token

    payload, node = verify_renewal_token(token, db=db)
    if not payload or not node:
        raise HTTPException(status_code=400, detail="操作链接无效或已过期。")

    if node.user_id != payload.get("uid"):
        raise HTTPException(status_code=404, detail="未找到对应的探针节点。")

    node_current_exp = to_iso_utc(node.expires_at) or ""
    token_cycle_exp = payload.get("nexp") or ""
    if node_current_exp and token_cycle_exp and token_cycle_exp != node_current_exp:
        raise HTTPException(status_code=400, detail="该节点已更新为新周期到期日，如需再次修改请前往探针面板。")

    date_str = body.expires_at.strip()
    if not date_str:
        raise HTTPException(status_code=400, detail="到期时间不能为空。")

    try:
        if len(date_str) == 10:
            new_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        else:
            new_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if new_date.tzinfo is None:
                new_date = new_date.replace(tzinfo=timezone.utc)
    except Exception:
        raise HTTPException(status_code=400, detail="无效的日期格式，请使用 YYYY-MM-DD。")

    node.expires_at = new_date
    node.expire_muted = False
    node.notified_expire_stages = []  # 重置已通知阶段，进入新周期
    db.commit()

    return {
        "ok": True,
        "expires_at": to_iso_utc(node.expires_at),
        "is_muted": False,
    }


def _make_demo_ping_history(base_telecom: float, base_unicom: float, base_mobile: float, count: int = 30) -> list:
    """生成真实的丢包色带与延迟历史。"""
    history = []
    for _ in range(count):
        # 偶尔轻微抖动或单点丢包
        is_loss_cm = random.random() < 0.05
        is_loss_cu = random.random() < 0.02
        history.append([
            {"name": "电信", "latency_ms": round(base_telecom + random.uniform(-4, 6), 1), "loss_rate": 0.0},
            {"name": "联通", "latency_ms": round(base_unicom + random.uniform(-3, 5), 1), "loss_rate": 0.0 if not is_loss_cu else 5.0},
            {"name": "移动", "latency_ms": round(base_mobile + random.uniform(-5, 8), 1), "loss_rate": 0.0 if not is_loss_cm else 3.2},
        ])
    return history


@router.post("/demo")
def load_demo_nodes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一键为当前用户载入高度仿真的演示节点集群。"""
    now = utcnow()

    demo_configs = [
        {
            "name": "香港 CMI",
            "country": "hk",
            "group_name": "主力",
            "tags": ["主力", "V4", "V6", "CMI", "三网优化"],
            "os_type": "debian",
            "cpu_cores": 2,
            "price": 39.0,
            "currency": "CNY",
            "billing_cycle": "monthly",
            "expires_at": now + timedelta(days=20),
            "traffic_limit_gb": 1024.0,
            "cpu_percent": 10.82,
            "ram_used": int(942 * 1024 * 1024),
            "ram_total": int(2048 * 1024 * 1024),
            "disk_used": int(15.2 * 1024 * 1024 * 1024),
            "disk_total": int(40.0 * 1024 * 1024 * 1024),
            "load_1": 0.22,
            "load_5": 0.18,
            "load_15": 0.15,
            "net_rx_rate": 1.68 * 1024 * 1024,
            "net_tx_rate": 1.51 * 1024 * 1024,
            "net_rx_total": int(1.33 * 1024 * 1024 * 1024 * 1024),
            "net_tx_total": int(1.11 * 1024 * 1024 * 1024 * 1024),
            "uptime_seconds": 63 * 86400 + 14200,
            "ping": (45.0, 42.0, 19.0),
        },
        {
            "name": "东京 软银",
            "country": "jp",
            "group_name": "主力",
            "tags": ["主力", "V4", "V6", "原生IP"],
            "os_type": "ubuntu",
            "cpu_cores": 2,
            "price": 6.99,
            "currency": "USD",
            "billing_cycle": "monthly",
            "expires_at": now + timedelta(days=11),
            "traffic_limit_gb": 2048.0,
            "cpu_percent": 29.73,
            "ram_used": int(2.32 * 1024 * 1024 * 1024),
            "ram_total": int(4.00 * 1024 * 1024 * 1024),
            "disk_used": int(26.4 * 1024 * 1024 * 1024),
            "disk_total": int(60.0 * 1024 * 1024 * 1024),
            "load_1": 0.59,
            "load_5": 0.45,
            "load_15": 0.38,
            "net_rx_rate": 3.22 * 1024 * 1024,
            "net_tx_rate": 2.43 * 1024 * 1024,
            "net_rx_total": int(5.23 * 1024 * 1024 * 1024 * 1024),
            "net_tx_total": int(4.37 * 1024 * 1024 * 1024 * 1024),
            "uptime_seconds": 27 * 86400 + 29300,
            "ping": (77.0, 59.0, 113.0),
        },
        {
            "name": "洛杉矶 CN2 GIA",
            "country": "us",
            "group_name": "主力",
            "tags": ["主力", "V4", "CN2 GIA"],
            "os_type": "debian",
            "cpu_cores": 1,
            "price": 49.99,
            "currency": "USD",
            "billing_cycle": "annually",
            "expires_at": now + timedelta(days=96),
            "traffic_limit_gb": 1024.0,
            "cpu_percent": 14.70,
            "ram_used": int(645 * 1024 * 1024),
            "ram_total": int(1024 * 1024 * 1024),
            "disk_used": int(10.4 * 1024 * 1024 * 1024),
            "disk_total": int(20.0 * 1024 * 1024 * 1024),
            "load_1": 0.15,
            "load_5": 0.12,
            "load_15": 0.08,
            "net_rx_rate": 797 * 1024,
            "net_tx_rate": 1.62 * 1024 * 1024,
            "net_rx_total": int(2.87 * 1024 * 1024 * 1024 * 1024),
            "net_tx_total": int(2.39 * 1024 * 1024 * 1024 * 1024),
            "uptime_seconds": 112 * 86400 + 48100,
            "ping": (135.0, 147.0, 146.0),
        },
        {
            "name": "新加坡 9929",
            "country": "sg",
            "group_name": "主力",
            "tags": ["主力", "V4", "V6", "9929"],
            "os_type": "debian",
            "cpu_cores": 2,
            "price": 25.0,
            "currency": "CNY",
            "billing_cycle": "monthly",
            "expires_at": now + timedelta(days=3),
            "traffic_limit_gb": 512.0,
            "cpu_percent": 26.51,
            "ram_used": int(840 * 1024 * 1024),
            "ram_total": int(2048 * 1024 * 1024),
            "disk_used": int(11.6 * 1024 * 1024 * 1024),
            "disk_total": int(40.0 * 1024 * 1024 * 1024),
            "load_1": 0.53,
            "load_5": 0.47,
            "load_15": 0.40,
            "net_rx_rate": 527 * 1024,
            "net_tx_rate": 852 * 1024,
            "net_rx_total": int(708 * 1024 * 1024 * 1024),
            "net_tx_total": int(592 * 1024 * 1024 * 1024),
            "uptime_seconds": 41 * 86400 + 19000,
            "ping": (89.0, 61.0, 90.0),
        },
        {
            "name": "法兰克福 大盘鸡",
            "country": "de",
            "group_name": "吃灰",
            "tags": ["吃灰", "V4", "V6", "存储"],
            "os_type": "alpine",
            "cpu_cores": 1,
            "price": 4.99,
            "currency": "EUR",
            "billing_cycle": "monthly",
            "expires_at": now + timedelta(days=16),
            "traffic_limit_gb": None,
            "cpu_percent": 3.50,
            "ram_used": int(220 * 1024 * 1024),
            "ram_total": int(1024 * 1024 * 1024),
            "disk_used": int(335 * 1024 * 1024 * 1024),
            "disk_total": int(500 * 1024 * 1024 * 1024),
            "load_1": 0.14,
            "load_5": 0.10,
            "load_15": 0.05,
            "net_rx_rate": 87.6 * 1024,
            "net_tx_rate": 60.3 * 1024,
            "net_rx_total": int(423 * 1024 * 1024 * 1024),
            "net_tx_total": int(354 * 1024 * 1024 * 1024),
            "uptime_seconds": 205 * 86400 + 51000,
            "ping": (218.0, 226.0, 207.0),
        },
        {
            "name": "圣何塞 年付鸡",
            "country": "us",
            "group_name": "吃灰",
            "tags": ["吃灰", "V4", "4837"],
            "os_type": "ubuntu",
            "cpu_cores": 1,
            "price": 10.99,
            "currency": "USD",
            "billing_cycle": "annually",
            "expires_at": now + timedelta(days=57),
            "traffic_limit_gb": 1024.0,
            "cpu_percent": 1.60,
            "ram_used": int(276 * 1024 * 1024),
            "ram_total": int(1024 * 1024 * 1024),
            "disk_used": int(5.75 * 1024 * 1024 * 1024),
            "disk_total": int(25.0 * 1024 * 1024 * 1024),
            "load_1": 0.02,
            "load_5": 0.03,
            "load_15": 0.01,
            "net_rx_rate": 11.3 * 1024,
            "net_tx_rate": 5.46 * 1024,
            "net_rx_total": int(65.7 * 1024 * 1024 * 1024),
            "net_tx_total": int(54.9 * 1024 * 1024 * 1024),
            "uptime_seconds": 71 * 86400 + 12000,
            "ping": (174.0, 142.0, 202.0),
        },
    ]

    created_nodes = []
    for cfg in demo_configs:
        token = f"demo_{secrets.token_urlsafe(24)}"
        ping_hist = _make_demo_ping_history(*cfg["ping"])
        latest_ping = ping_hist[-1]

        node = UserNode(
            user_id=user.id,
            token=token,
            name=cfg["name"],
            country=cfg["country"],
            group_name=cfg["group_name"],
            tags=cfg["tags"],
            os_type=cfg["os_type"],
            cpu_cores=cfg["cpu_cores"],
            price=cfg["price"],
            currency=cfg["currency"],
            billing_cycle=cfg["billing_cycle"],
            expires_at=cfg["expires_at"],
            expire_notify_enabled=True,
            expire_notify_stages=[15, 7, 3, 1],
            notified_expire_stages=[],
            traffic_limit_gb=cfg["traffic_limit_gb"],
            is_online=True,
            is_demo=True,
            is_public=True,
            last_seen_at=now,
            cached_status={
                "cpu_percent": cfg["cpu_percent"],
                "ram_used_bytes": cfg["ram_used"],
                "ram_total_bytes": cfg["ram_total"],
                "disk_used_bytes": cfg["disk_used"],
                "disk_total_bytes": cfg["disk_total"],
                "load_1": cfg["load_1"],
                "load_5": cfg["load_5"],
                "load_15": cfg["load_15"],
                "net_rx_rate": cfg["net_rx_rate"],
                "net_tx_rate": cfg["net_tx_rate"],
                "net_rx_total": cfg["net_rx_total"],
                "net_tx_total": cfg["net_tx_total"],
                "uptime_seconds": cfg["uptime_seconds"],
                "agent_version": CURRENT_AGENT_VERSION,
                "auto_update": True,
                "ping_stats": latest_ping,
                "ping_history": ping_hist,
            },
        )
        db.add(node)
        created_nodes.append((node, cfg, ping_hist))

    db.commit()

    # 为每个节点生成 24 小时历史趋势快照（每 30 分钟一个点，共 48 个时序点）
    for node, cfg, _ in created_nodes:
        db.refresh(node)
        snapshots = []
        for i in range(48, 0, -1):
            ts = now - timedelta(minutes=i * 30)
            noise = random.uniform(-0.15, 0.15)
            # 基础波动
            cpu_val = max(1.0, min(95.0, cfg["cpu_percent"] * (1 + noise)))
            p_ct, p_cu, p_cm = cfg["ping"]
            p_stats = [
                {"name": "电信", "latency_ms": round(p_ct * (1 + noise * 0.5), 1), "loss_rate": 0.0},
                {"name": "联通", "latency_ms": round(p_cu * (1 + noise * 0.5), 1), "loss_rate": 0.0 if random.random() > 0.03 else 2.5},
                {"name": "移动", "latency_ms": round(p_cm * (1 + noise * 0.5), 1), "loss_rate": 0.0 if random.random() > 0.05 else 5.0},
            ]
            snap = NodeSnapshot(
                node_id=node.id,
                recorded_at=ts,
                cpu_percent=round(cpu_val, 2),
                ram_used_bytes=cfg["ram_used"],
                ram_total_bytes=cfg["ram_total"],
                disk_used_bytes=cfg["disk_used"],
                disk_total_bytes=cfg["disk_total"],
                load_1=round(cfg["load_1"] * (1 + noise), 2),
                load_5=cfg["load_5"],
                load_15=cfg["load_15"],
                net_rx_rate=max(0, cfg["net_rx_rate"] * (1 + noise)),
                net_tx_rate=max(0, cfg["net_tx_rate"] * (1 + noise)),
                net_rx_total=cfg["net_rx_total"],
                net_tx_total=cfg["net_tx_total"],
                uptime_seconds=cfg["uptime_seconds"] - (i * 1800),
                ping_stats=p_stats,
            )
            snapshots.append(snap)
        db.add_all(snapshots)

    db.commit()
    return {"ok": True, "count": len(created_nodes)}


@router.delete("/demo")
def clear_demo_nodes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一键清空用户的所有演示节点及其快照。"""
    demo_node_ids = db.scalars(
        select(UserNode.id).where(UserNode.user_id == user.id, UserNode.is_demo == True)
    ).all()
    if demo_node_ids:
        db.execute(delete(NodeSnapshot).where(NodeSnapshot.node_id.in_(demo_node_ids)))
        db.execute(delete(UserNode).where(UserNode.id.in_(demo_node_ids)))
        db.commit()
    return {"ok": True}


@router.get("/nodes/{node_id}/history")
def get_node_history(
    node_id: int,
    hours: int = Query(default=24, ge=1, le=168),
    share: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """查询节点过去 24 小时的 Ping 与系统负载趋势图表数据。"""
    node = db.get(UserNode, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    # 权限检查：私有必须拥有，公开需验证 share token
    if share:
        target_user = db.scalar(
            select(User).where(User.monitor_share_token == share, User.monitor_public_enabled == True)
        )
        if not target_user or target_user.id != node.user_id:
            raise HTTPException(status_code=403, detail="无权访问该节点监控历史")
        if not node.is_public:
            raise HTTPException(status_code=403, detail="无权访问该节点监控历史")
    else:
        if not user or user.id != node.user_id:
            raise HTTPException(status_code=403, detail="无权访问该节点监控历史")

    since = utcnow() - timedelta(hours=hours)
    snapshots = db.scalars(
        select(NodeSnapshot)
        .where(NodeSnapshot.node_id == node_id, NodeSnapshot.recorded_at >= since)
        .order_by(NodeSnapshot.recorded_at.asc())
    ).all()

    # 降采样抽样，保证前端图表渲染流畅（最多返回 100 个点）
    max_points = 96
    if len(snapshots) > max_points:
        step = math.ceil(len(snapshots) / max_points)
        sampled = snapshots[::step]
    else:
        sampled = snapshots

    points = []
    for s in sampled:
        points.append({
            "timestamp": to_iso_utc(s.recorded_at),
            "cpu_percent": s.cpu_percent,
            "ram_percent": round((s.ram_used_bytes / s.ram_total_bytes * 100) if s.ram_total_bytes > 0 else 0, 1),
            "disk_percent": round((s.disk_used_bytes / s.disk_total_bytes * 100) if s.disk_total_bytes > 0 else 0, 1),
            "load_1": s.load_1,
            "net_rx_rate": s.net_rx_rate,
            "net_tx_rate": s.net_tx_rate,
            "ping_stats": s.ping_stats or [],
        })

    return {
        "node_id": node_id,
        "name": node.name,
        "points": points,
    }


@router.post("/report")
def report_metrics(
    payload: NodeReport,
    x_node_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """VPS Agent 客户端数据上报接口。"""
    if not x_node_token:
        raise HTTPException(status_code=401, detail="Missing X-Node-Token header")

    node = db.scalar(select(UserNode).where(UserNode.token == x_node_token.strip()))
    if not node:
        raise HTTPException(status_code=404, detail="Invalid node token")

    now = utcnow()
    node.is_online = True
    node.last_seen_at = now
    if payload.cpu_cores:
        node.cpu_cores = payload.cpu_cores
    if payload.os_type:
        if payload.os_type.lower() != "linux" or not node.os_type or node.os_type == "linux":
            node.os_type = payload.os_type.lower()
    if payload.os_version is not None:
        node.os_version = payload.os_version
    if payload.arch:
        node.arch = payload.arch

    # 保留最近 30 条 ping 历史色带
    cached = node.cached_status or {}
    ping_history = cached.get("ping_history", [])
    if payload.ping_stats:
        ping_history.append([p.model_dump() for p in payload.ping_stats])
        if len(ping_history) > 30:
            ping_history = ping_history[-30:]

    cpu_pct = float(payload.cpu_percent if payload.cpu_percent is not None else 0.0)

    # 提取并记录内核版本
    kernel_ver = payload.kernel_version
    if not kernel_ver and payload.os_type == "linux" and payload.os_version:
        kernel_ver = payload.os_version

    node.cached_status = {
        "cpu_percent": cpu_pct,
        "ram_used_bytes": payload.ram_used_bytes,
        "ram_total_bytes": payload.ram_total_bytes,
        "swap_used_bytes": payload.swap_used_bytes,
        "swap_total_bytes": payload.swap_total_bytes,
        "disk_used_bytes": payload.disk_used_bytes,
        "disk_total_bytes": payload.disk_total_bytes,
        "load_1": payload.load_1,
        "load_5": payload.load_5,
        "load_15": payload.load_15,
        "net_rx_rate": payload.net_rx_rate,
        "net_tx_rate": payload.net_tx_rate,
        "net_rx_total": payload.net_rx_total,
        "net_tx_total": payload.net_tx_total,
        "uptime_seconds": payload.uptime_seconds,
        "kernel_version": kernel_ver,
        "agent_version": payload.agent_version or CURRENT_AGENT_VERSION,
        "auto_update": payload.auto_update,
        "ping_stats": [p.model_dump() for p in payload.ping_stats],
        "ping_history": ping_history,
    }

    # 写入快照表（节流：至少间隔 10 秒写入一条快照）
    last_snap = db.scalar(
        select(NodeSnapshot)
        .where(NodeSnapshot.node_id == node.id)
        .order_by(NodeSnapshot.recorded_at.desc())
        .limit(1)
    )
    should_insert_snapshot = True
    if last_snap:
        snap_time = last_snap.recorded_at
        if snap_time.tzinfo is None:
            snap_time = snap_time.replace(tzinfo=timezone.utc)
        if (now - snap_time).total_seconds() < 10:
            should_insert_snapshot = False

    if should_insert_snapshot:
        snap = NodeSnapshot(
            node_id=node.id,
            recorded_at=now,
            cpu_percent=cpu_pct,
            ram_used_bytes=payload.ram_used_bytes,
            ram_total_bytes=payload.ram_total_bytes,
            swap_used_bytes=payload.swap_used_bytes,
            swap_total_bytes=payload.swap_total_bytes,
            disk_used_bytes=payload.disk_used_bytes,
            disk_total_bytes=payload.disk_total_bytes,
            load_1=payload.load_1,
            load_5=payload.load_5,
            load_15=payload.load_15,
            net_rx_rate=payload.net_rx_rate,
            net_tx_rate=payload.net_tx_rate,
            net_rx_total=payload.net_rx_total,
            net_tx_total=payload.net_tx_total,
            uptime_seconds=payload.uptime_seconds,
            ping_stats=[p.model_dump() for p in payload.ping_stats],
        )
        db.add(snap)
        db.execute(
            delete(NodeSnapshot)
            .where(
                NodeSnapshot.node_id == node.id,
                NodeSnapshot.recorded_at < now - SNAPSHOT_TTL,
            )
            .execution_options(synchronize_session=False)
        )

    db.commit()

    upgrade_available = False
    if payload.auto_update and payload.agent_version and payload.agent_version != CURRENT_AGENT_VERSION:
        upgrade_available = True

    return {
        "status": "ok",
        "latest_version": CURRENT_AGENT_VERSION,
        "upgrade_available": upgrade_available,
    }


def get_agent_python_code() -> str:
    """返回纯标准库实现的最新版 Python 探针核心程序代码。

    TODO: 针对 64MB/128MB 等极限小内存/NAT 机器，后续规划推出 Go 编写的单文件静态二进制 Agent，
          将常驻内存 (RSS) 压缩至 2-4MB 以内（详见 docs/TODO.md）。
    """
    return f"""import os, sys, time, json, platform, subprocess, urllib.request, urllib.error, concurrent.futures, collections, py_compile

AGENT_VERSION = "{CURRENT_AGENT_VERSION}"
AUTO_UPDATE_ENABLED = os.environ.get("GOVPS_AUTO_UPDATE", "1").strip().lower() not in ("0", "false", "no", "off")

TOKEN = os.environ.get("GOVPS_TOKEN", "").strip()
while TOKEN.startswith("GOVPS_TOKEN="):
    TOKEN = TOKEN[len("GOVPS_TOKEN="):].strip()
TOKEN = TOKEN.strip().strip('"').strip("'")

SERVER_URL = os.environ.get("GOVPS_SERVER_URL", "https://govps.xyz").strip()
while SERVER_URL.startswith("GOVPS_SERVER_URL="):
    SERVER_URL = SERVER_URL[len("GOVPS_SERVER_URL="):].strip()
SERVER_URL = SERVER_URL.strip().strip('"').strip("'")
if not SERVER_URL.startswith("http://") and not SERVER_URL.startswith("https://"):
    SERVER_URL = "https://govps.xyz"

PING_COUNT = int(os.environ.get("GOVPS_PING_COUNT", "10"))
PING_WINDOW = int(os.environ.get("GOVPS_PING_WINDOW", "10"))

PING_TARGETS = [
    {{"name": "电信", "hosts": ["202.96.209.133", "202.96.128.86"]}},   # 上海电信 / 广东电信
    {{"name": "联通", "hosts": ["112.64.120.1", "119.167.0.1"]}},       # 上海联通 / 山东联通骨干
    {{"name": "移动", "hosts": ["221.130.33.52", "211.136.192.6"]}},   # 北京移动 / 广东移动
]

_rolling_ping_records = collections.defaultdict(lambda: collections.deque(maxlen=PING_WINDOW))
_last_update_check = 0.0
_UPDATE_CHECK_COOLDOWN = 1800.0  # 自动更新最小冷却时间 30 分钟，避免高频打服务端

def check_and_apply_update(target_version=None):
    \"\"\"检测并执行平滑自更新：原子替换本地文件并通过 os.execv 原地重载，保持 PID 与进程生命周期。\"\"\"
    global _last_update_check
    now = time.time()
    if not AUTO_UPDATE_ENABLED:
        return
    if now - _last_update_check < _UPDATE_CHECK_COOLDOWN:
        return
    _last_update_check = now

    script_path = os.path.abspath(__file__)
    install_dir = os.path.dirname(script_path)
    if not os.path.isdir(install_dir):
        return

    update_url = f"{{SERVER_URL.rstrip('/')}}/api/monitor/agent.py"
    tmp_path = os.path.join(install_dir, "govps_agent.py.new")

    try:
        req = urllib.request.Request(
            update_url,
            headers={{
                "User-Agent": f"GoVPS-Agent/{{AGENT_VERSION}}",
                "X-Node-Token": TOKEN,
            }},
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            if res.status != 200:
                return
            new_code = res.read().decode("utf-8")

        # 校验新脚本完整性与特征
        if "AGENT_VERSION" not in new_code or "def main():" not in new_code:
            return

        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        # 语法校验：若编译出错抛出异常放弃覆盖
        py_compile.compile(tmp_path, doraise=True)

        # 原子覆盖替换
        os.replace(tmp_path, script_path)
        os.chmod(script_path, 0o755)

        # 同步静默拉取最新的 agent.sh 维护脚本
        try:
            sh_url = f"{{SERVER_URL.rstrip('/')}}/api/monitor/agent.sh"
            sh_path = os.path.join(install_dir, "agent.sh")
            sh_tmp = os.path.join(install_dir, "agent.sh.new")
            sh_req = urllib.request.Request(sh_url, headers={{"User-Agent": f"GoVPS-Agent/{{AGENT_VERSION}}"}})
            with urllib.request.urlopen(sh_req, timeout=10) as res_sh:
                if res_sh.status == 200:
                    sh_code = res_sh.read().decode("utf-8")
                    if "GOVPS" in sh_code:
                        with open(sh_tmp, "w", encoding="utf-8") as f:
                            f.write(sh_code)
                        os.replace(sh_tmp, sh_path)
                        os.chmod(sh_path, 0o755)
        except Exception:
            pass

        print(f"[{{time.strftime('%Y-%m-%d %H:%M:%S')}}] 探针已成功自动平滑升级至版本 {{target_version or '最新版'}}，正在原地重载...", flush=True)
        # 原地替换当前进程镜像，PID 不变，平滑进入新版循环
        os.execv(sys.executable, [sys.executable, script_path] + sys.argv[1:])
    except Exception as e:
        print(f"[{{time.strftime('%Y-%m-%d %H:%M:%S')}}] 自动更新执行异常: {{e}}", file=sys.stderr, flush=True)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def get_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            return int(float(f.readline().split()[0]))
    except Exception:
        return 0

_prev_cpu = None

def get_cpu_info():
    global _prev_cpu
    cores = os.cpu_count() or 1
    load1, load5, load15 = 0.0, 0.0, 0.0
    try:
        l1, l5, l15 = os.getloadavg()
        load1, load5, load15 = round(l1, 2), round(l5, 2), round(l15, 2)
    except Exception:
        pass

    def read_stat():
        with open("/proc/stat", "r") as f:
            fields = [float(x) for x in f.readline().strip().split()[1:]]
        idle = fields[3] + (fields[4] if len(fields) > 4 else 0.0)
        total = sum(fields)
        return idle, total

    cpu_pct = 0.0
    try:
        idle_now, total_now = read_stat()
        if _prev_cpu is not None:
            prev_idle, prev_total = _prev_cpu
            diff_idle = idle_now - prev_idle
            diff_total = total_now - prev_total
            if diff_total > 0:
                cpu_pct = max(0.0, min(100.0, round((1.0 - diff_idle / diff_total) * 100, 2)))
        else:
            time.sleep(0.2)
            i2, t2 = read_stat()
            diff_idle = i2 - idle_now
            diff_total = t2 - total_now
            if diff_total > 0:
                cpu_pct = max(0.0, min(100.0, round((1.0 - diff_idle / diff_total) * 100, 2)))
            idle_now, total_now = i2, t2
        _prev_cpu = (idle_now, total_now)
    except Exception:
        if cores > 0:
            cpu_pct = max(0.0, min(100.0, round((load1 / cores) * 100, 2)))

    # 若瞬时全空闲但存在系统负载，基于负载合理映射避免全 0 显示
    if cpu_pct <= 0.0 and load1 > 0:
        cpu_pct = max(0.1, min(100.0, round((load1 / cores) * 100, 2)))

    return cpu_pct, cores, load1, load5, load15

def get_mem_info():
    ram_used, ram_total = 0, 0
    swap_used, swap_total = 0, 0
    try:
        mem = {{}}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = int(parts[1].strip().split()[0]) * 1024
                    mem[k] = v
        ram_total = mem.get("MemTotal", 0)
        ram_avail = mem.get("MemAvailable", mem.get("MemFree", 0) + mem.get("Buffers", 0) + mem.get("Cached", 0))
        ram_used = max(0, ram_total - ram_avail)
        swap_total = mem.get("SwapTotal", 0)
        swap_free = mem.get("SwapFree", 0)
        swap_used = max(0, swap_total - swap_free)
    except Exception:
        pass
    return ram_used, ram_total, swap_used, swap_total

def get_disk_info():
    try:
        st = os.statvfs("/")
        total = st.f_blocks * st.f_frsize
        avail = st.f_bavail * st.f_frsize
        used = total - avail
        return used, total
    except Exception:
        return 0, 0

_prev_net = None
_prev_net_time = None

def get_net_info():
    global _prev_net, _prev_net_time
    rx_bytes, tx_bytes = 0, 0
    try:
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if ":" not in line:
                    continue
                iface, data = line.split(":", 1)
                if iface.strip() in ("lo", "docker0"):
                    continue
                cols = data.strip().split()
                rx_bytes += int(cols[0])
                tx_bytes += int(cols[8])
    except Exception:
        pass

    now = time.time()
    rx_rate, tx_rate = 0.0, 0.0
    if _prev_net and _prev_net_time:
        dt = max(0.1, now - _prev_net_time)
        rx_rate = max(0.0, (rx_bytes - _prev_net[0]) / dt)
        tx_rate = max(0.0, (tx_bytes - _prev_net[1]) / dt)

    _prev_net = (rx_bytes, tx_bytes)
    _prev_net_time = now
    return rx_rate, tx_rate, rx_bytes, tx_bytes

def get_os_info():
    os_name = platform.system().lower()
    os_version = ""
    kernel_ver = platform.release()
    try:
        found_distro = False
        for p in ["/etc/os-release", "/usr/lib/os-release"]:
            if os.path.exists(p):
                data = {{}}
                with open(p, "r") as f:
                    for line in f:
                        if "=" in line:
                            k, v = line.strip().split("=", 1)
                            data[k.strip()] = v.strip().strip('"').strip("'")
                distro_id = data.get("ID", "").lower()
                if distro_id:
                    os_name = distro_id
                    found_distro = True
                ver = data.get("VERSION_ID", "")
                if not ver:
                    raw_v = data.get("VERSION", "")
                    if raw_v:
                        ver = raw_v.split()[0]
                if ver:
                    os_version = ver
                break

        if not found_distro:
            if os.path.exists("/etc/debian_version"):
                try:
                    with open("/etc/debian_version", "r") as f:
                        os_name = "debian"
                        os_version = f.read().strip()
                except Exception:
                    pass
            elif os.path.exists("/etc/alpine-release"):
                try:
                    with open("/etc/alpine-release", "r") as f:
                        os_name = "alpine"
                        os_version = f.read().strip()
                except Exception:
                    pass
            elif os.path.exists("/etc/redhat-release"):
                try:
                    with open("/etc/redhat-release", "r") as f:
                        os_name = "centos"
                        for part in f.read().strip().split():
                            if part and part[0].isdigit():
                                os_version = part
                                break
                except Exception:
                    pass

        # 归一化发行版名称
        if "ubuntu" in os_name:
            os_name = "ubuntu"
        elif "debian" in os_name:
            os_name = "debian"
        elif any(x in os_name for x in ["alma", "rocky", "centos", "rhel"]):
            os_name = "centos"
        elif "alpine" in os_name:
            os_name = "alpine"
        elif "arch" in os_name:
            os_name = "arch"
        elif "fedora" in os_name:
            os_name = "fedora"
    except Exception:
        pass
    return os_name, os_version, kernel_ver

def run_ping_target(target):
    cmd = ["ping", "-c", str(PING_COUNT), "-i", "0.2", "-W", "1", target]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode != 0 and "invalid" in res.stderr.lower():
            # 兼容极少数精简环境不支持浮点间隔的情况
            cmd = ["ping", "-c", str(PING_COUNT), "-W", "1", target]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
        out = res.stdout
        sent, recv, loss, rtt = PING_COUNT, 0, 100.0, 0.0
        for line in out.splitlines():
            if "packet loss" in line:
                for p in line.split(","):
                    p = p.strip()
                    if "transmitted" in p:
                        try:
                            sent = int(p.split()[0])
                        except Exception:
                            pass
                    elif "received" in p:
                        try:
                            recv = int(p.split()[0])
                        except Exception:
                            pass
                    elif "packet loss" in p:
                        try:
                            loss = float(p.replace("% packet loss", "").strip())
                        except Exception:
                            pass
            if "avg" in line and "/" in line:
                stats = line.split("=")[1].strip().split()[0].split("/")
                rtt = float(stats[1])
        return sent, recv, round(rtt, 1), round(loss, 1)
    except Exception:
        return PING_COUNT, 0, 0.0, 100.0

def run_ping_carrier(carrier_name, target_or_targets):
    if isinstance(target_or_targets, (list, tuple)):
        targets = [t for t in target_or_targets if t]
    else:
        targets = [target_or_targets]
    if not targets:
        return 0.0, 100.0

    chosen_sent, chosen_recv, chosen_rtt = PING_COUNT, 0, 0.0
    for target in targets:
        sent, recv, rtt, loss = run_ping_target(target)
        chosen_sent, chosen_recv, chosen_rtt = sent, recv, rtt
        if loss < 100.0:
            break

    # 滑动窗口累计多轮探测（默认保存最近 10 轮采样，共 100 个 ICMP 样本，时间跨度 5 分钟）
    dq = _rolling_ping_records[carrier_name]
    dq.append({{"sent": chosen_sent, "recv": chosen_recv, "rtt": chosen_rtt}})

    total_sent = sum(item["sent"] for item in dq)
    total_recv = sum(item["recv"] for item in dq)
    if total_sent == 0:
        return 0.0, 100.0

    # 滑动窗口丢包率：具备精准的 1.0% 阶梯粒度
    window_loss = round(max(0.0, min(100.0, ((total_sent - total_recv) / total_sent) * 100.0)), 1)

    # 延迟加权平均
    valid_items = [item for item in dq if item["recv"] > 0 and item["rtt"] > 0]
    if valid_items:
        weighted_sum = sum(item["rtt"] * item["recv"] for item in valid_items)
        weight_count = sum(item["recv"] for item in valid_items)
        avg_rtt = round(weighted_sum / weight_count, 1) if weight_count > 0 else 0.0
    else:
        avg_rtt = 0.0

    return avg_rtt, window_loss

def run_ping(target_or_targets):
    return run_ping_carrier("default", target_or_targets)

def main():
    if not TOKEN:
        print("Error: GOVPS_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    url = f"{{SERVER_URL.rstrip('/')}}/api/monitor/report"

    # 探测操作系统发行版与内核信息
    os_type, os_version, kernel_version = get_os_info()

    # 首次采样网络与 CPU 基线
    get_net_info()
    get_cpu_info()

    ping_cycle = 0
    cached_ping_stats = []

    print(f"[{{time.strftime('%Y-%m-%d %H:%M:%S')}}] GoVPS Agent v{{AGENT_VERSION}} 启动成功 (自动更新: {{'已启用' if AUTO_UPDATE_ENABLED else '已禁用'}})", flush=True)

    while True:
        try:
            cpu_pct, cores, l1, l5, l15 = get_cpu_info()
            r_used, r_total, sw_used, sw_total = get_mem_info()
            d_used, d_total = get_disk_info()
            rx_rate, tx_rate, rx_total, tx_total = get_net_info()
            uptime = get_uptime()

            # 每 30 秒执行一次 Ping 测速（主循环 10 秒，每 3 次循环运行一次）
            if ping_cycle % 3 == 0:
                def probe(pt):
                    targets = pt.get("hosts") or [pt.get("host")]
                    lat, loss = run_ping_carrier(pt["name"], targets)
                    return {{
                        "name": pt["name"],
                        "latency_ms": lat,
                        "loss_rate": loss,
                    }}
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        cached_ping_stats = list(executor.map(probe, PING_TARGETS))
                except Exception:
                    pass
            ping_cycle += 1

            payload = {{
                "cpu_percent": cpu_pct,
                "cpu_cores": cores,
                "ram_used_bytes": r_used,
                "ram_total_bytes": r_total,
                "swap_used_bytes": sw_used,
                "swap_total_bytes": sw_total,
                "disk_used_bytes": d_used,
                "disk_total_bytes": d_total,
                "load_1": l1,
                "load_5": l5,
                "load_15": l15,
                "net_rx_rate": rx_rate,
                "net_tx_rate": tx_rate,
                "net_rx_total": rx_total,
                "net_tx_total": tx_total,
                "uptime_seconds": uptime,
                "os_type": os_type,
                "os_version": os_version,
                "kernel_version": kernel_version,
                "arch": platform.machine(),
                "agent_version": AGENT_VERSION,
                "auto_update": AUTO_UPDATE_ENABLED,
                "ping_stats": cached_ping_stats,
            }}

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={{
                    "Content-Type": "application/json",
                    "X-Node-Token": TOKEN,
                    "User-Agent": f"Mozilla/5.0 (compatible; GoVPS-Agent/{{AGENT_VERSION}}; +https://govps.xyz)",
                }}
            )
            with urllib.request.urlopen(req, timeout=8) as res:
                if res.status == 200:
                    try:
                        resp_data = json.loads(res.read().decode("utf-8"))
                        if resp_data.get("upgrade_available") and AUTO_UPDATE_ENABLED:
                            check_and_apply_update(resp_data.get("latest_version"))
                    except Exception:
                        pass
        except Exception as e:
            print(f"[{{time.strftime('%Y-%m-%d %H:%M:%S')}}] 数据上报异常: {{e}}", file=sys.stderr, flush=True)

        # 每日定期或心跳空闲时兜底检测自动更新（每 360 次循环约为 1 小时）
        if ping_cycle % 360 == 0 and AUTO_UPDATE_ENABLED:
            try:
                check_and_apply_update()
            except Exception:
                pass

        time.sleep(10)

if __name__ == "__main__":
    main()
"""


@router.api_route("/agent.py", methods=["GET", "HEAD"])
def get_agent_py():
    """动态返回纯原生 Python 3 的 Agent 探针核心执行代码。"""
    code = get_agent_python_code()
    return Response(
        content=code,
        media_type="text/x-python",
        headers={
            "X-Agent-Version": CURRENT_AGENT_VERSION,
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@router.api_route("/agent.sh", methods=["GET", "HEAD"])
def get_agent_script():
    """动态返回纯原生 Shell + Python3 的高兼容性 VPS 监控 Agent 安装与卸载脚本。"""
    py_code = get_agent_python_code()
    script_content = r"""#!/usr/bin/env bash
# ==============================================================================
# GoVPS Monitor Agent · 一键部署脚本
# 兼容 Debian, Ubuntu, CentOS, AlmaLinux, Rocky, Alpine, Arch, Fedora 等各类主流系统
# ==============================================================================
set -e

COLOR_GREEN='\033[0;32m'
COLOR_BLUE='\033[0;34m'
COLOR_RED='\033[0;31m'
COLOR_YELLOW='\033[1;33m'
COLOR_RESET='\033[0m'

INSTALL_DIR="/opt/govps-agent"
SERVICE_NAME="govps-agent"

print_info() { echo -e "${COLOR_BLUE}[INFO]${COLOR_RESET} $1"; }
print_ok()   { echo -e "${COLOR_GREEN}[OK]${COLOR_RESET} $1"; }
print_warn() { echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $1"; }
print_err()  { echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1"; }

TOKEN=""
SERVER_URL="https://govps.xyz"
ACTION="install"
AUTO_UPDATE="1"

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --url) SERVER_URL="$2"; shift 2 ;;
    --auto-update) AUTO_UPDATE="1"; shift ;;
    --no-auto-update) AUTO_UPDATE="0"; shift ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --update) ACTION="update"; shift ;;
    *) shift ;;
  esac
done

if [ "$ACTION" = "uninstall" ]; then
  print_info "正在卸载 GoVPS Agent..."
  if command -v systemctl &>/dev/null; then
    systemctl stop $SERVICE_NAME || true
    systemctl disable $SERVICE_NAME || true
    rm -f /etc/systemd/system/${SERVICE_NAME}.service
    systemctl daemon-reload || true
  fi
  rm -f /etc/cron.d/govps-agent-update /etc/cron.daily/govps-agent-update 2>/dev/null || true
  pkill -f "govps_agent.py" || true
  rm -rf "$INSTALL_DIR"
  print_ok "GoVPS Agent 卸载完成！"
  exit 0
fi

if [ "$ACTION" = "update" ]; then
  print_info "正在检测并更新 GoVPS Agent..."
  if [ -z "$TOKEN" ] && [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
    SAVED_TOKEN=$(grep -E "^Environment=GOVPS_TOKEN=" /etc/systemd/system/${SERVICE_NAME}.service | head -n1 | sed -E 's/^Environment=(")?GOVPS_TOKEN=([^"]*)(")?/\2/' || true)
    SAVED_URL=$(grep -E "^Environment=GOVPS_SERVER_URL=" /etc/systemd/system/${SERVICE_NAME}.service | head -n1 | sed -E 's/^Environment=(")?GOVPS_SERVER_URL=([^"]*)(")?/\2/' || true)
    SAVED_AUTO=$(grep -E "^Environment=GOVPS_AUTO_UPDATE=" /etc/systemd/system/${SERVICE_NAME}.service | head -n1 | sed -E 's/^Environment=(")?GOVPS_AUTO_UPDATE=([^"]*)(")?/\2/' || true)
    [ -n "$SAVED_TOKEN" ] && TOKEN="$SAVED_TOKEN"
    [ -n "$SAVED_URL" ] && SERVER_URL="$SAVED_URL"
    [ -n "$SAVED_AUTO" ] && AUTO_UPDATE="$SAVED_AUTO"
  fi
  if [ -z "$TOKEN" ] && [ -f "$INSTALL_DIR/token" ]; then
    TOKEN=$(cat "$INSTALL_DIR/token" 2>/dev/null || true)
  fi
  if [ -f "$INSTALL_DIR/auto_update" ]; then
    AUTO_UPDATE=$(cat "$INSTALL_DIR/auto_update" 2>/dev/null || echo "1")
  fi

  # 防御性清洗 TOKEN 与 SERVER_URL 前缀
  while [[ "$TOKEN" =~ ^GOVPS_TOKEN= ]]; do
    TOKEN="${TOKEN#GOVPS_TOKEN=}"
  done
  TOKEN=$(echo "$TOKEN" | tr -d '"' | tr -d "'" | xargs)

  while [[ "$SERVER_URL" =~ ^GOVPS_SERVER_URL= ]]; do
    SERVER_URL="${SERVER_URL#GOVPS_SERVER_URL=}"
  done
  SERVER_URL=$(echo "$SERVER_URL" | tr -d '"' | tr -d "'" | xargs)
  [ -z "$SERVER_URL" ] && SERVER_URL="https://govps.xyz"

  if [ -z "$TOKEN" ]; then
    print_err "未找到当前节点的 Token 记录，请使用: bash agent.sh --token <YOUR_TOKEN> 重新安装更新。"
    exit 1
  fi
  # 仅当本脚本是从本地文件（如 /opt/govps-agent/agent.sh）执行时，尝试拉取服务端最新 agent.sh 链式重载
  if [ "${GOVPS_UPDATE_REEXEC:-0}" != "1" ] && [ -f "$0" ] && [ "$0" != "bash" ] && [ "$0" != "-bash" ] && [ -n "$SERVER_URL" ]; then
    export GOVPS_UPDATE_REEXEC=1
    TMP_SH=$(mktemp /tmp/govps-update.XXXXXX.sh 2>/dev/null || echo "/tmp/govps-update.sh")
    if curl -fsSL "${SERVER_URL}/api/monitor/agent.sh" -o "$TMP_SH" 2>/dev/null && [ -s "$TMP_SH" ] && grep -q "GOVPS" "$TMP_SH" 2>/dev/null; then
      bash "$TMP_SH" --update --token "$TOKEN" --url "$SERVER_URL"
      RET=$?
      rm -f "$TMP_SH"
      exit $RET
    fi
    rm -f "$TMP_SH"
  fi
fi

# 全局清理防御
while [[ "$TOKEN" =~ ^GOVPS_TOKEN= ]]; do
  TOKEN="${TOKEN#GOVPS_TOKEN=}"
done
TOKEN=$(echo "$TOKEN" | tr -d '"' | tr -d "'" | xargs)

while [[ "$SERVER_URL" =~ ^GOVPS_SERVER_URL= ]]; do
  SERVER_URL="${SERVER_URL#GOVPS_SERVER_URL=}"
done
SERVER_URL=$(echo "$SERVER_URL" | tr -d '"' | tr -d "'" | xargs)
[ -z "$SERVER_URL" ] && SERVER_URL="https://govps.xyz"

if [ -z "$TOKEN" ]; then
  print_err "未提供节点 Token！请使用: bash agent.sh --token <YOUR_TOKEN>"
  exit 1
fi

print_info "开始部署 GoVPS 探针 Agent..."

# 检查 Python3 与网络工具
if ! command -v python3 &>/dev/null; then
  print_warn "未检测到 python3，尝试通过包管理器安装..."
  if command -v apt-get &>/dev/null; then
    apt-get update -y && apt-get install -y python3 iputils-ping curl
  elif command -v dnf &>/dev/null; then
    dnf install -y python3 iputils curl
  elif command -v yum &>/dev/null; then
    yum install -y python3 iputils curl
  elif command -v apk &>/dev/null; then
    apk add --no-cache python3 iputils curl
  elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm python iputils curl
  elif command -v zypper &>/dev/null; then
    zypper --non-interactive install python3 iputils curl
  else
    print_err "未检测到支持的包管理器，请手动安装 Python 3 之后重试。"
    exit 1
  fi
fi

PYTHON_BIN=$(command -v python3 || command -v python || echo "/usr/bin/python3")

mkdir -p "$INSTALL_DIR"
echo "$TOKEN" > "$INSTALL_DIR/token"
echo "$AUTO_UPDATE" > "$INSTALL_DIR/auto_update"
chmod 600 "$INSTALL_DIR/token"
if [ -f "$0" ] && grep -q "GOVPS" "$0" 2>/dev/null; then
  cp -f "$0" "$INSTALL_DIR/agent.sh" 2>/dev/null || true
else
  curl -fsSL "${SERVER_URL}/api/monitor/agent.sh" -o "$INSTALL_DIR/agent.sh" 2>/dev/null || true
fi
chmod +x "$INSTALL_DIR/agent.sh" 2>/dev/null || true

cat << 'EOF' > "$INSTALL_DIR/govps_agent.py"
""" + py_code + r"""
EOF

chmod +x "$INSTALL_DIR/govps_agent.py"

# 配置 systemd 守护进程
if command -v systemctl &>/dev/null; then
  cat << EOF > /etc/systemd/system/${SERVICE_NAME}.service
[Unit]
Description=GoVPS Monitor Agent
After=network.target

[Service]
Type=simple
Environment=GOVPS_TOKEN=${TOKEN}
Environment=GOVPS_SERVER_URL=${SERVER_URL}
Environment=GOVPS_AUTO_UPDATE=${AUTO_UPDATE}
ExecStart=${PYTHON_BIN} ${INSTALL_DIR}/govps_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable $SERVICE_NAME
  systemctl restart $SERVICE_NAME
  print_ok "GoVPS Agent 已作为 systemd 服务启动！"

  print_info "正在验证初始心跳上报连通性..."
  sleep 2
  if systemctl is-active --quiet $SERVICE_NAME; then
    print_ok "Agent 服务运行状态正常 (active)！"
  else
    print_warn "服务启动异常，请查看: journalctl -u $SERVICE_NAME -n 20"
  fi
else
  # 降级 nohup 后台运行
  pkill -f "govps_agent.py" || true
  GOVPS_TOKEN="$TOKEN" GOVPS_SERVER_URL="$SERVER_URL" GOVPS_AUTO_UPDATE="$AUTO_UPDATE" nohup "$PYTHON_BIN" "$INSTALL_DIR/govps_agent.py" >/dev/null 2>&1 &
  print_ok "GoVPS Agent 已在后台启动！"
fi

# 配置每日自动更新维护定时任务（Cron 兜底）
if [ "$AUTO_UPDATE" = "1" ] && [ -d "/etc/cron.d" ] && [ -w "/etc/cron.d" ]; then
  cat << 'EOF_CRON' > /etc/cron.d/govps-agent-update
# GoVPS Agent 每日自动维护与检查更新
0 4 * * * root /opt/govps-agent/agent.sh --update >/dev/null 2>&1
EOF_CRON
  chmod 644 /etc/cron.d/govps-agent-update 2>/dev/null || true
fi
if [ "$AUTO_UPDATE" = "0" ]; then
  rm -f /etc/cron.d/govps-agent-update /etc/cron.daily/govps-agent-update 2>/dev/null || true
fi

print_ok "================================================="
print_ok "  GoVPS 探针监控 Agent 部署/更新成功！"
print_ok "  数据每 10 秒自动上报，三网延迟每 30 秒测速一次（5 分钟 100 样本滑动窗口）。"
if [ "$AUTO_UPDATE" = "1" ]; then
  print_ok "  自动更新: 已开启 (检测到新版本将自动平滑热升级，无需手动干预)"
else
  print_ok "  自动更新: 已禁用 (可通过 bash /opt/govps-agent/agent.sh --auto-update 重新开启)"
fi
print_ok "  如需手动更新: curl -fsSL https://govps.xyz/api/monitor/agent.sh | sudo bash -s -- --update"
print_ok "  如需卸载: sudo bash /opt/govps-agent/agent.sh --uninstall"
print_ok "================================================="
"""
    return Response(content=script_content, media_type="text/x-shellscript")
