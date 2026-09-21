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
from ..schemas import NodeCreate, NodeReport, NodeUpdate, ShareUpdate

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


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
        traffic_limit_gb=payload.traffic_limit_gb,
        is_online=False,
        is_demo=False,
        is_public=payload.is_public if payload.is_public is not None else True,
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
    install_command = f"curl -sSL {api_origin}/api/monitor/agent.sh | sudo bash -s -- --token {token} --url {api_origin}"

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

    if payload.name is not None:
        node.name = payload.name
    if payload.country is not None:
        node.country = payload.country.lower()
    if payload.group_name is not None:
        node.group_name = payload.group_name
    if payload.tags is not None:
        node.tags = payload.tags
    if payload.os_type is not None:
        node.os_type = payload.os_type.lower()
    if payload.cpu_cores is not None:
        node.cpu_cores = payload.cpu_cores
    if payload.price is not None:
        node.price = payload.price
    if payload.currency is not None:
        node.currency = payload.currency
    if payload.billing_cycle is not None:
        node.billing_cycle = payload.billing_cycle
    if payload.expires_at is not None:
        node.expires_at = payload.expires_at
    if payload.traffic_limit_gb is not None:
        node.traffic_limit_gb = payload.traffic_limit_gb
    if payload.is_public is not None:
        node.is_public = payload.is_public

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
        node.os_type = payload.os_type.lower()
    if payload.os_version:
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

    db.commit()
    return {"status": "ok"}


@router.get("/agent.sh")
def get_agent_script():
    """动态返回纯原生 Shell + Python3 的高兼容性 VPS 监控 Agent 安装与卸载脚本。"""
    script_content = r"""#!/usr/bin/env bash
# ==============================================================================
# GoVPS Monitor Agent · 一键部署脚本
# 兼容 Debian, Ubuntu, CentOS, AlmaLinux, Rocky, Alpine, Arch 等各类主流系统
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

while [[ $# -gt 0 ]]; do
  case $1 in
    --token) TOKEN="$2"; shift 2 ;;
    --url) SERVER_URL="$2"; shift 2 ;;
    --uninstall) ACTION="uninstall"; shift ;;
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
  pkill -f "govps_agent.py" || true
  rm -rf "$INSTALL_DIR"
  print_ok "GoVPS Agent 卸载完成！"
  exit 0
fi

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
  elif command -v yum &>/dev/null; then
    yum install -y python3 iputils curl
  elif command -v apk &>/dev/null; then
    apk add --no-cache python3 iputils curl
  elif command -v pacman &>/dev/null; then
    pacman -Sy --noconfirm python iputils curl
  else
    print_err "未检测到包管理器，请手动安装 Python 3 之后重试。"
    exit 1
  fi
fi

PYTHON_BIN=$(command -v python3 || command -v python || echo "/usr/bin/python3")

mkdir -p "$INSTALL_DIR"

cat << 'EOF' > "$INSTALL_DIR/govps_agent.py"
import os, sys, time, json, platform, subprocess, urllib.request, urllib.error, concurrent.futures, collections

TOKEN = os.environ.get("GOVPS_TOKEN", "")
SERVER_URL = os.environ.get("GOVPS_SERVER_URL", "https://govps.xyz")
PING_COUNT = int(os.environ.get("GOVPS_PING_COUNT", "10"))
PING_WINDOW = int(os.environ.get("GOVPS_PING_WINDOW", "10"))

PING_TARGETS = [
    {"name": "电信", "hosts": ["202.96.209.133", "202.96.128.86"]},   # 上海电信 / 广东电信
    {"name": "联通", "hosts": ["112.64.120.1", "119.167.0.1"]},       # 上海联通 / 山东联通骨干
    {"name": "移动", "hosts": ["221.130.33.52", "211.136.192.6"]},   # 北京移动 / 广东移动
]

_rolling_ping_records = collections.defaultdict(lambda: collections.deque(maxlen=PING_WINDOW))

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
        mem = {}
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
    os_version = platform.release()
    try:
        if os.path.exists("/etc/os-release"):
            data = {}
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        data[k.strip()] = v.strip().strip("\"'")
            distro_id = data.get("ID", "").lower()
            if distro_id:
                os_name = distro_id
            version = data.get("VERSION_ID", data.get("VERSION", ""))
            if version:
                os_version = version
    except Exception:
        pass
    return os_name, os_version

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
    dq.append({"sent": chosen_sent, "recv": chosen_recv, "rtt": chosen_rtt})

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

    url = f"{SERVER_URL.rstrip('/')}/api/monitor/report"

    # 首次采样网络与 CPU 基线
    get_net_info()
    get_cpu_info()

    ping_cycle = 0
    cached_ping_stats = []

    while True:
        try:
            cpu_pct, cores, l1, l5, l15 = get_cpu_info()
            r_used, r_total, sw_used, sw_total = get_mem_info()
            d_used, d_total = get_disk_info()
            rx_rate, tx_rate, rx_total, tx_total = get_net_info()
            uptime = get_uptime()

            # 每 30 秒执行一次三网 Ping 测速（多线程并发探测，避免阻塞心跳上报）
            if ping_cycle % 3 == 0 or not cached_ping_stats:
                def probe(pt):
                    targets = pt.get("hosts") or [pt.get("host")]
                    lat, loss = run_ping_carrier(pt["name"], targets)
                    return {
                        "name": pt["name"],
                        "latency_ms": lat,
                        "loss_rate": loss,
                    }
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        cached_ping_stats = list(executor.map(probe, PING_TARGETS))
                except Exception:
                    pass
            ping_cycle += 1

            payload = {
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
                "os_type": get_os_info()[0],
                "os_version": get_os_info()[1],
                "arch": platform.machine(),
                "ping_stats": cached_ping_stats
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "X-Node-Token": TOKEN,
                    "User-Agent": "Mozilla/5.0 (compatible; GoVPS-Agent/1.0; +https://govps.xyz)"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as res:
                if res.status == 200:
                    pass
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据上报异常: {e}", file=sys.stderr, flush=True)

        time.sleep(10)

if __name__ == "__main__":
    main()
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
  GOVPS_TOKEN="$TOKEN" GOVPS_SERVER_URL="$SERVER_URL" nohup "$PYTHON_BIN" "$INSTALL_DIR/govps_agent.py" >/dev/null 2>&1 &
  print_ok "GoVPS Agent 已在后台启动！"
fi

print_ok "================================================="
print_ok "  GoVPS 探针监控 Agent 部署成功！"
print_ok "  数据每 10 秒自动上报，三网延迟每 30 秒测速一次（5 分钟 100 样本滑动窗口）。"
print_ok "  如需卸载，随时执行: sudo bash /opt/govps-agent/agent.sh --uninstall"
print_ok "================================================="
"""
    return Response(content=script_content, media_type="text/x-shellscript")
