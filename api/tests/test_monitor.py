"""GoVPS 探针监控路由自动化测试。"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import ExchangeRate, NodeSnapshot, User, UserNode


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        # 确保基础汇率存在
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
        user = db.scalar(select(User).where(User.email == "monitor_user@example.com"))
        if not user:
            user = User(
                email="monitor_user@example.com",
                api_token="test_monitor_token_12345",
                view_mode="card",
                currency_mode="CNY",
                monitor_public_enabled=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def test_unauthorized_access(client):
    res = client.get("/api/monitor/nodes")
    assert res.status_code == 401


def test_crud_and_reporting(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 1. 创建节点
    payload = {
        "name": "测试节点-香港",
        "country": "hk",
        "group_name": "主力",
        "tags": ["主力", "V4", "CMI"],
        "os_type": "debian",
        "cpu_cores": 2,
        "price": 30.0,
        "currency": "USD",
        "billing_cycle": "monthly",
        "traffic_limit_gb": 1024.0,
    }
    create_res = client.post("/api/monitor/nodes", json=payload, headers=headers)
    assert create_res.status_code == 200
    data = create_res.json()
    node = data["node"]
    node_id = node["id"]
    token = data["token"]
    assert "install_command" in data
    assert "-fsSL" in data["install_command"]
    assert node["name"] == "测试节点-香港"
    assert node["is_public"] is False

    # 2. 列表查询
    list_res = client.get("/api/monitor/nodes", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert len(list_data["nodes"]) >= 1
    assert list_data["summary"]["total_count"] >= 1

    # 3. Agent 上报
    report_payload = {
        "cpu_percent": 15.5,
        "cpu_cores": 2,
        "ram_used_bytes": 1024 * 1024 * 512,
        "ram_total_bytes": 1024 * 1024 * 1024,
        "disk_used_bytes": 1024 * 1024 * 1024 * 10,
        "disk_total_bytes": 1024 * 1024 * 1024 * 50,
        "load_1": 0.35,
        "load_5": 0.20,
        "load_15": 0.15,
        "net_rx_rate": 204800,
        "net_tx_rate": 102400,
        "net_rx_total": 500000000,
        "net_tx_total": 300000000,
        "uptime_seconds": 86400 * 5,
        "agent_version": "1.0.0",
        "auto_update": True,
        "ping_stats": [
            {"name": "电信", "latency_ms": 42.5, "loss_rate": 0.0},
            {"name": "联通", "latency_ms": 38.2, "loss_rate": 0.0},
            {"name": "移动", "latency_ms": 18.9, "loss_rate": 0.0},
        ],
    }
    report_res = client.post(
        "/api/monitor/report",
        json=report_payload,
        headers={"X-Node-Token": token},
    )
    assert report_res.status_code == 200
    res_json = report_res.json()
    assert res_json["status"] == "ok"
    assert res_json["upgrade_available"] is True
    assert res_json["latest_version"] == "1.3.1"

    # 3.1 上报已是最新版本，应无升级提示
    report_payload["agent_version"] = "1.3.1"
    report_res2 = client.post(
        "/api/monitor/report",
        json=report_payload,
        headers={"X-Node-Token": token},
    )
    assert report_res2.status_code == 200
    assert report_res2.json()["upgrade_available"] is False

    # 4. 再次获取列表，验证状态已更新为在线且指标正确
    updated_res = client.get("/api/monitor/nodes", headers=headers)
    target = next(n for n in updated_res.json()["nodes"] if n["id"] == node_id)
    assert target["is_online"] is True
    assert target["metrics"]["cpu_percent"] == 15.5
    assert target["metrics"]["uptime_days"] == 5
    assert target["metrics"]["agent_version"] == "1.3.1"
    assert target["metrics"]["auto_update"] is True

    # 5. 历史曲线查询
    hist_res = client.get(f"/api/monitor/nodes/{node_id}/history", headers=headers)
    assert hist_res.status_code == 200
    points = hist_res.json()["points"]
    assert len(points) >= 1
    assert points[-1]["cpu_percent"] == 15.5

    # 6. 删除节点
    del_res = client.delete(f"/api/monitor/nodes/{node_id}", headers=headers)
    assert del_res.status_code == 200


def test_demo_and_share(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 1. 载入演示节点
    demo_res = client.post("/api/monitor/demo", headers=headers)
    assert demo_res.status_code == 200
    assert demo_res.json()["count"] >= 4

    # 2. 验证演示节点在线与数据饱满
    list_res = client.get("/api/monitor/nodes", headers=headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["summary"]["online_count"] >= 4
    assert data["summary"]["bandwidth"]["total_rate"] > 0
    demo_node = next(n for n in data["nodes"] if n.get("is_demo"))

    # 3. 开启公开分享
    share_res = client.post("/api/monitor/share?enabled=true", headers=headers)
    assert share_res.status_code == 200
    share_token = share_res.json()["share_token"]
    assert share_token is not None

    # 4. 游客通过 share_token 免登录只读访问
    guest_res = client.get(f"/api/monitor/nodes?share={share_token}")
    assert guest_res.status_code == 200
    guest_data = guest_res.json()
    assert guest_data["user_info"]["is_owner"] is False
    assert len(guest_data["nodes"]) >= 4

    # 4.1 测试选择性公开节点（仅公开第一个节点）
    select_res = client.post(
        "/api/monitor/share",
        json={"enabled": True, "public_node_ids": [demo_node["id"]]},
        headers=headers,
    )
    assert select_res.status_code == 200
    guest_res2 = client.get(f"/api/monitor/nodes?share={share_token}")
    assert guest_res2.status_code == 200
    assert len(guest_res2.json()["nodes"]) == 1
    assert guest_res2.json()["nodes"][0]["id"] == demo_node["id"]

    # 5. 游客访问单节点历史曲线
    guest_hist = client.get(f"/api/monitor/nodes/{demo_node['id']}/history?share={share_token}")
    assert guest_hist.status_code == 200
    assert len(guest_hist.json()["points"]) >= 10

    other = next(n for n in data["nodes"] if n["id"] != demo_node["id"])
    hidden_hist = client.get(f"/api/monitor/nodes/{other['id']}/history?share={share_token}")
    assert hidden_hist.status_code == 403

    # 6. 清理演示节点
    clear_res = client.delete("/api/monitor/demo", headers=headers)
    assert clear_res.status_code == 200


def test_agent_script_distribution(client):
    res = client.get("/api/monitor/agent.sh")
    assert res.status_code == 200
    assert "GoVPS Monitor Agent" in res.text
    assert "python3" in res.text
    assert "iputils-ping" in res.text
    assert "Environment=LC_ALL=C" in res.text
    assert "Environment=LANG=C" in res.text
    assert "Environment=LANGUAGE=" in res.text
    assert "--uninstall" in res.text
    assert "--update" in res.text
    assert "-fsSL" in res.text
    assert "--auto-update" in res.text
    assert "--no-auto-update" in res.text


def test_agent_python_distribution(client):
    res = client.get("/api/monitor/agent.py")
    assert res.status_code == 200
    assert res.headers.get("X-Agent-Version") == "1.3.1"
    assert "check_and_apply_update" in res.text
    assert "os.execv" in res.text
    assert "py_compile" in res.text
    assert 'ping_env["LC_ALL"] = "C"' in res.text
    assert 'ping_env["LANG"] = "C"' in res.text
    assert 'ping_env.pop("LANGUAGE", None)' in res.text
    assert "env=ping_env" in res.text
    # 确保返回的代码在语法上完全有效
    compiled = compile(res.text, "govps_agent.py", "exec")
    assert compiled is not None


def test_update_node_clears_expiry_and_quota(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}
    create_res = client.post(
        "/api/monitor/nodes",
        json={
            "name": "可清空",
            "country": "jp",
            "expires_at": "2026-12-01T00:00:00.000Z",
            "traffic_limit_gb": 512,
        },
        headers=headers,
    )
    assert create_res.status_code == 200
    node_id = create_res.json()["node"]["id"]
    assert create_res.json()["node"]["expires_at"] is not None
    assert create_res.json()["node"]["traffic_limit_gb"] == 512

    upd = client.put(
        f"/api/monitor/nodes/{node_id}",
        json={"expires_at": None, "traffic_limit_gb": None},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["node"]["expires_at"] is None
    assert upd.json()["node"]["traffic_limit_gb"] is None


def test_report_prunes_old_snapshots(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}
    create_res = client.post(
        "/api/monitor/nodes",
        json={"name": "清理快照", "country": "sg"},
        headers=headers,
    )
    node = create_res.json()["node"]
    token = create_res.json()["token"]
    old = datetime.now(timezone.utc) - timedelta(days=5)
    with Session(engine) as db:
        db.add(
            NodeSnapshot(
                node_id=node["id"],
                recorded_at=old,
                cpu_percent=1.0,
            )
        )
        db.commit()
        assert db.scalar(select(func.count()).select_from(NodeSnapshot).where(NodeSnapshot.node_id == node["id"])) == 1

    client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 2.0,
            "ram_used_bytes": 1,
            "ram_total_bytes": 2,
            "disk_used_bytes": 1,
            "disk_total_bytes": 2,
            "uptime_seconds": 10,
        },
        headers={"X-Node-Token": token},
    )
    with Session(engine) as db:
        rows = db.scalars(select(NodeSnapshot).where(NodeSnapshot.node_id == node["id"])).all()
        assert len(rows) == 1
        assert rows[0].recorded_at.replace(tzinfo=timezone.utc) > old


