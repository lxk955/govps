"""VPS 探针公网 IP 展示与分享脱敏自动化测试。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import ExchangeRate, User, UserNode
from app.routers.monitor import is_valid_public_ip, mask_ip


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        if not db.scalar(select(ExchangeRate).where(ExchangeRate.code == "USD")):
            db.add(ExchangeRate(code="USD", units_per_usd=1.0, source="auto"))
        if not db.scalar(select(ExchangeRate).where(ExchangeRate.code == "CNY")):
            db.add(ExchangeRate(code="CNY", units_per_usd=7.2, source="auto"))
        db.commit()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_user():
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "public_ip_user@example.com"))
        if not user:
            user = User(
                email="public_ip_user@example.com",
                api_token="test_public_ip_token_999",
                view_mode="card",
                currency_mode="CNY",
                monitor_public_enabled=False,
                monitor_share_ip_mode="mask",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def test_is_valid_public_ip():
    """测试公网 IP 合法性过滤。"""
    assert is_valid_public_ip("8.8.8.8") == "8.8.8.8"
    assert is_valid_public_ip("2400:cb00:2048:1::c629:d7a2") == "2400:cb00:2048:1::c629:d7a2"
    # 私网、回环、保留地址应返回 None
    assert is_valid_public_ip("127.0.0.1") is None
    assert is_valid_public_ip("192.168.1.1") is None
    assert is_valid_public_ip("10.0.0.1") is None
    assert is_valid_public_ip("172.16.0.1") is None
    assert is_valid_public_ip("100.64.0.1") is None  # CGNAT
    assert is_valid_public_ip("169.254.1.1") is None  # Link-local
    assert is_valid_public_ip("224.0.0.1") is None  # Multicast
    assert is_valid_public_ip("240.0.0.1") is None  # Reserved
    assert is_valid_public_ip("::1") is None  # IPv6 Loopback
    assert is_valid_public_ip("fe80::1") is None  # IPv6 Link-local
    assert is_valid_public_ip("fec0::1") is None  # IPv6 Site-local (deprecated)
    assert is_valid_public_ip("invalid-ip") is None
    assert is_valid_public_ip(None) is None


def test_mask_ip_helper():
    """测试 IP 脱敏函数。"""
    # 正常 IPv4
    assert mask_ip("123.45.67.89") == "123.45.*.*"
    assert mask_ip("1.1.1.1") == "1.1.*.*"
    assert mask_ip("  10.0.0.1  ") == "10.0.*.*"

    # 正常 IPv6
    assert mask_ip("2400:cb00:2048:1::c629:d7a2") == "2400:cb00:****"
    assert mask_ip("2001:db8:85a3::8a2e:370:7334") == "2001:db8:****"

    # 压缩格式 IPv6（安全展开后脱敏，不泄漏主机位）
    assert mask_ip("2400::c629:d7a2") == "2400:0:****"

    # 空值与特殊值
    assert mask_ip(None) is None
    assert mask_ip("") is None
    assert mask_ip("   ") is None
    assert mask_ip("not-an-ip") == "****"


def test_create_and_update_node_with_public_ip(client, test_user):
    """测试创建与更新节点时保存公网 IP。"""
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 1. 创建带 public_ip 的节点
    res = client.post(
        "/api/monitor/nodes",
        headers=headers,
        json={
            "name": "测试节点-IP",
            "country": "hk",
            "group_name": "主力",
            "public_ip": "103.152.220.18",
        },
    )
    assert res.status_code == 200
    data = res.json()
    node_id = data["node"]["id"]
    assert data["node"]["public_ip"] == "103.152.220.18"

    # 2. 拥有者查看节点列表，返回原始真实 IP
    res = client.get("/api/monitor/nodes", headers=headers)
    assert res.status_code == 200
    nodes = res.json()["nodes"]
    target = next(n for n in nodes if n["id"] == node_id)
    assert target["public_ip"] == "103.152.220.18"
    assert res.json()["user_info"]["share_ip_mode"] == "mask"

    # 3. 编辑节点修改 IP
    res = client.put(
        f"/api/monitor/nodes/{node_id}",
        headers=headers,
        json={"public_ip": "118.238.203.45"},
    )
    assert res.status_code == 200
    assert res.json()["node"]["public_ip"] == "118.238.203.45"

    # 4. 清除 IP（置空）
    res = client.put(
        f"/api/monitor/nodes/{node_id}",
        headers=headers,
        json={"public_ip": ""},
    )
    assert res.status_code == 200
    assert res.json()["node"]["public_ip"] is None

    # 5. 非法格式或私网/保留 IP 地址在创建与更新时严格返回 400
    res = client.post(
        "/api/monitor/nodes",
        headers=headers,
        json={"name": "非法IP测试", "country": "hk", "public_ip": "192.168.1.1"},
    )
    assert res.status_code == 400
    assert "公网 IP" in res.json()["detail"]

    res = client.put(
        f"/api/monitor/nodes/{node_id}",
        headers=headers,
        json={"public_ip": "invalid-ip-string"},
    )
    assert res.status_code == 400
    assert "公网 IP" in res.json()["detail"]


def test_share_ip_modes(client, test_user):
    """测试分享的三种 IP 策略 (mask, hide, show)。"""
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 创建一个节点用于分享
    res = client.post(
        "/api/monitor/nodes",
        headers=headers,
        json={
            "name": "分享测试节点",
            "country": "jp",
            "public_ip": "118.238.203.45",
            "is_public": True,
        },
    )
    node_id = res.json()["node"]["id"]

    # 1. 开启分享，设置 share_ip_mode = mask (默认)
    res = client.post(
        "/api/monitor/share",
        headers=headers,
        json={
            "enabled": True,
            "public_node_ids": [node_id],
            "share_ip_mode": "mask",
        },
    )
    assert res.status_code == 200
    share_token = res.json()["share_token"]
    assert res.json()["share_ip_mode"] == "mask"

    # 访客访问：验证 IP 已脱敏
    res = client.get(f"/api/monitor/nodes?share={share_token}")
    assert res.status_code == 200
    shared_nodes = res.json()["nodes"]
    assert len(shared_nodes) >= 1
    target = next(n for n in shared_nodes if n["id"] == node_id)
    assert target["public_ip"] == "118.238.*.*"
    assert res.json()["user_info"]["is_owner"] is False
    assert res.json()["user_info"]["share_ip_mode"] == "mask"

    # 2. 更改分享策略为 hide (完全隐藏)
    res = client.post(
        "/api/monitor/share",
        headers=headers,
        json={
            "enabled": True,
            "public_node_ids": [node_id],
            "share_ip_mode": "hide",
        },
    )
    assert res.status_code == 200
    assert res.json()["share_ip_mode"] == "hide"

    # 访客访问：验证 public_ip 为 None
    res = client.get(f"/api/monitor/nodes?share={share_token}")
    assert res.status_code == 200
    target = next(n for n in res.json()["nodes"] if n["id"] == node_id)
    assert target["public_ip"] is None
    assert res.json()["user_info"]["share_ip_mode"] == "hide"

    # 3. 更改分享策略为 show (完整公开)
    res = client.post(
        "/api/monitor/share",
        headers=headers,
        json={
            "enabled": True,
            "public_node_ids": [node_id],
            "share_ip_mode": "show",
        },
    )
    assert res.status_code == 200
    assert res.json()["share_ip_mode"] == "show"

    # 访客访问：验证 public_ip 为真实 IP
    res = client.get(f"/api/monitor/nodes?share={share_token}")
    assert res.status_code == 200
    target = next(n for n in res.json()["nodes"] if n["id"] == node_id)
    assert target["public_ip"] == "118.238.203.45"

    # 拥有者访问：始终能看到完整真实 IP
    res = client.get("/api/monitor/nodes", headers=headers)
    assert res.status_code == 200
    owner_target = next(n for n in res.json()["nodes"] if n["id"] == node_id)
    assert owner_target["public_ip"] == "118.238.203.45"


def test_agent_report_public_ip(client, test_user):
    """测试 Agent 上报公网 IP 与回退客户端真实 IP。"""
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 创建节点（无 IP）
    res = client.post(
        "/api/monitor/nodes",
        headers=headers,
        json={"name": "心跳测试节点", "country": "us"},
    )
    assert res.status_code == 200
    node_token = res.json()["token"]
    node_id = res.json()["node"]["id"]
    assert res.json()["node"]["public_ip"] is None

    # 1. Agent 上报带 public_ip
    report_headers = {"X-Node-Token": node_token}
    res = client.post(
        "/api/monitor/report",
        headers=report_headers,
        json={
            "cpu_percent": 15.2,
            "ram_used_bytes": 1024 * 1024 * 100,
            "ram_total_bytes": 1024 * 1024 * 1024,
            "disk_used_bytes": 0,
            "disk_total_bytes": 1024 * 1024 * 1024,
            "net_rx_rate": 0,
            "net_tx_rate": 0,
            "net_rx_total": 0,
            "net_tx_total": 0,
            "uptime_seconds": 120,
            "public_ip": "45.76.100.200",
        },
    )
    assert res.status_code == 200

    # 验证节点 public_ip 已更新
    res = client.get("/api/monitor/nodes", headers=headers)
    target = next(n for n in res.json()["nodes"] if n["id"] == node_id)
    assert target["public_ip"] == "45.76.100.200"

    # 2. 如果上报没有带 public_ip（如探测未完成或网络异常），不信任反代 IP 兜底，避免代理出口泄露
    # 先清空 IP
    client.put(f"/api/monitor/nodes/{node_id}", headers=headers, json={"public_ip": ""})

    res = client.post(
        "/api/monitor/report",
        headers={**report_headers, "cf-connecting-ip": "104.28.16.55"},
        json={
            "cpu_percent": 10.0,
            "ram_used_bytes": 100,
            "ram_total_bytes": 1000,
            "disk_used_bytes": 0,
            "disk_total_bytes": 1000,
            "net_rx_rate": 0,
            "net_tx_rate": 0,
            "net_rx_total": 0,
            "net_tx_total": 0,
            "uptime_seconds": 130,
        },
    )
    assert res.status_code == 200

    res = client.get("/api/monitor/nodes", headers=headers)
    target = next(n for n in res.json()["nodes"] if n["id"] == node_id)
    assert target["public_ip"] is None

    # 3. 用户手动修改 IP 为自定义 IP "1.1.1.1"
    client.put(f"/api/monitor/nodes/{node_id}", headers=headers, json={"public_ip": "1.1.1.1"})
    res = client.get("/api/monitor/nodes", headers=headers)
    assert next(n for n in res.json()["nodes"] if n["id"] == node_id)["public_ip"] == "1.1.1.1"

    # Agent 心跳上报真实探测 IP "45.76.100.200"，绝不会覆盖用户手动设置的 "1.1.1.1"
    res = client.post(
        "/api/monitor/report",
        headers=report_headers,
        json={
            "cpu_percent": 12.0,
            "ram_used_bytes": 100,
            "ram_total_bytes": 1000,
            "disk_used_bytes": 0,
            "disk_total_bytes": 1000,
            "net_rx_rate": 0,
            "net_tx_rate": 0,
            "net_rx_total": 0,
            "net_tx_total": 0,
            "uptime_seconds": 150,
            "public_ip": "45.76.100.200",
        },
    )
    assert res.status_code == 200
    res = client.get("/api/monitor/nodes", headers=headers)
    assert next(n for n in res.json()["nodes"] if n["id"] == node_id)["public_ip"] == "1.1.1.1"

    # 4. 用户清空 IP（置空），下一次心跳会自动重新捕获并更新为 Agent 探测到的真实 IP
    client.put(f"/api/monitor/nodes/{node_id}", headers=headers, json={"public_ip": ""})
    res = client.post(
        "/api/monitor/report",
        headers=report_headers,
        json={
            "cpu_percent": 12.0,
            "ram_used_bytes": 100,
            "ram_total_bytes": 1000,
            "disk_used_bytes": 0,
            "disk_total_bytes": 1000,
            "net_rx_rate": 0,
            "net_tx_rate": 0,
            "net_rx_total": 0,
            "net_tx_total": 0,
            "uptime_seconds": 160,
            "public_ip": "45.76.100.200",
        },
    )
    assert res.status_code == 200
    res = client.get("/api/monitor/nodes", headers=headers)
    assert next(n for n in res.json()["nodes"] if n["id"] == node_id)["public_ip"] == "45.76.100.200"


def test_demo_nodes_public_ip(client, test_user):
    """测试载入演示节点时预置的公网 IP。"""
    headers = {"Authorization": f"Bearer {test_user.api_token}"}
    res = client.post("/api/monitor/demo", headers=headers)
    assert res.status_code == 200

    res = client.get("/api/monitor/nodes", headers=headers)
    assert res.status_code == 200
    demo_nodes = [n for n in res.json()["nodes"] if n["is_demo"]]
    assert len(demo_nodes) >= 6
    # 验证演示节点均具有合法 public_ip
    for n in demo_nodes:
        assert n["public_ip"] is not None
        assert "." in n["public_ip"]
