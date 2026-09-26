"""GoVPS 流量周期与重置逻辑自动化测试。"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import ExchangeRate, User, UserNode
from app.routers.monitor import calculate_traffic_cycle


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
        user = db.scalar(select(User).where(User.email == "traffic_test_user@example.com"))
        if not user:
            user = User(
                email="traffic_test_user@example.com",
                api_token="test_traffic_token_12345",
                view_mode="card",
                currency_mode="CNY",
                monitor_public_enabled=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def test_calculate_traffic_cycle_anchors():
    """测试不同到期日、月末截断、闰年与跨年计算。"""
    # 1. 锚定 15 号
    now_mar20 = datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc)
    exp_oct15 = datetime(2026, 10, 15, 23, 59, 59, tzinfo=timezone.utc)
    start, end, days_left = calculate_traffic_cycle(exp_oct15, now_mar20)
    assert start == datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert days_left == 26

    now_mar10 = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    start2, end2, days_left2 = calculate_traffic_cycle(exp_oct15, now_mar10)
    assert start2 == datetime(2026, 2, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert end2 == datetime(2026, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert days_left2 == 5

    # 2. 闰年测试：2024 年 1 月 31 日到期，2 月有 29 天
    now_feb2024 = datetime(2024, 2, 10, 0, 0, 0, tzinfo=timezone.utc)
    exp_jan31 = datetime(2024, 1, 31, 0, 0, 0, tzinfo=timezone.utc)
    start_leap, end_leap, _ = calculate_traffic_cycle(exp_jan31, now_feb2024)
    assert start_leap == datetime(2024, 1, 31, 0, 0, 0, tzinfo=timezone.utc)
    assert end_leap == datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)

    # 闰年 3 月：锚点自动恢复为 31 日，起点对齐 2 月 29 日
    now_mar2024 = datetime(2024, 3, 5, 0, 0, 0, tzinfo=timezone.utc)
    start_mar, end_mar, _ = calculate_traffic_cycle(exp_jan31, now_mar2024)
    assert start_mar == datetime(2024, 2, 29, 0, 0, 0, tzinfo=timezone.utc)
    assert end_mar == datetime(2024, 3, 31, 0, 0, 0, tzinfo=timezone.utc)

    # 3. 跨年测试：12 月到 1 月
    now_jan2027 = datetime(2027, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
    exp_dec15 = datetime(2026, 12, 15, 0, 0, 0, tzinfo=timezone.utc)
    start_cross, end_cross, _ = calculate_traffic_cycle(exp_dec15, now_jan2027)
    assert start_cross == datetime(2026, 12, 15, 0, 0, 0, tzinfo=timezone.utc)
    assert end_cross == datetime(2027, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # 4. expires_at 为 None，12 月回退测试
    now_dec2026 = datetime(2026, 12, 20, 0, 0, 0, tzinfo=timezone.utc)
    start_none, end_none, _ = calculate_traffic_cycle(None, now_dec2026)
    assert start_none == datetime(2026, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert end_none == datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_traffic_accumulation_and_direction(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 1. 创建节点，指定仅计出站 (traffic_direction="out")
    create_res = client.post(
        "/api/monitor/nodes",
        json={
            "name": "Traffic-Test-Node",
            "traffic_limit_gb": 1000,
            "traffic_direction": "out",
            "expires_at": "2026-10-15T00:00:00Z",
        },
        headers=headers,
    )
    assert create_res.status_code == 200
    res_data = create_res.json()
    node_data = res_data["node"]
    node_id = node_data["id"]
    agent_token = res_data["token"]
    assert node_data["traffic_direction"] == "out"

    agent_headers = {"X-Node-Token": agent_token}

    # 2. 首次上报：开机历史累计 500MB rx, 200MB tx, uptime=1000s
    # 建立基线，周期内用量为 0
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 10.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 200 * 1024 * 1024,
            "net_rx_total": 500 * 1024 * 1024,
            "uptime_seconds": 1000,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    get_res = client.get("/api/monitor/nodes", headers=headers)
    assert get_res.status_code == 200
    node = next(n for n in get_res.json()["nodes"] if n["id"] == node_id)
    assert node["cycle_traffic_rx"] == 0
    assert node["cycle_traffic_tx"] == 0
    assert node["cycle_traffic_used_bytes"] == 0

    # 3. 正常增量上报：增加 100MB rx, 50MB tx, uptime=1010s
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 15.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 250 * 1024 * 1024,  # +50MB
            "net_rx_total": 600 * 1024 * 1024,  # +100MB
            "uptime_seconds": 1010,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    get_res = client.get("/api/monitor/nodes", headers=headers)
    node = next(n for n in get_res.json()["nodes"] if n["id"] == node_id)
    assert node["cycle_traffic_rx"] == 100 * 1024 * 1024
    assert node["cycle_traffic_tx"] == 50 * 1024 * 1024
    # 因为设置了 traffic_direction="out"，used_bytes 应该仅计算 tx
    assert node["cycle_traffic_used_bytes"] == 50 * 1024 * 1024

    # 4. 模拟容器销毁/网卡抖动（计数下降，但系统未重启 uptime=1020s）：
    # 出站计数从 250MB 降至 240MB，绝不能虚增 240MB！
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 12.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 240 * 1024 * 1024,  # 下降了 10MB
            "net_rx_total": 600 * 1024 * 1024,
            "uptime_seconds": 1020,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    get_res = client.get("/api/monitor/nodes", headers=headers)
    node = next(n for n in get_res.json()["nodes"] if n["id"] == node_id)
    # 用量保持 50MB，未虚增
    assert node["cycle_traffic_tx"] == 50 * 1024 * 1024

    # 4.1 容器/网卡恢复，回升到 251MB（比下跌前的 250MB 实际仅增长 1MB）：
    # 验证高水位基线保护生效，只累加实际新增的 1MB，而不是 251-240=11MB
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 12.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 251 * 1024 * 1024,  # 回升并净增 1MB
            "net_rx_total": 600 * 1024 * 1024,
            "uptime_seconds": 1030,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    get_res = client.get("/api/monitor/nodes", headers=headers)
    node = next(n for n in get_res.json()["nodes"] if n["id"] == node_id)
    # 严格断言仅累加 1MB，达到 51MB
    assert node["cycle_traffic_tx"] == 51 * 1024 * 1024

    # 5. 修改到期时间：验证到期日变更绝不会清零已累积的周期流量
    update_exp_res = client.put(
        f"/api/monitor/nodes/{node_id}",
        json={"expires_at": "2026-11-20T23:59:59Z"},
        headers=headers,
    )
    assert update_exp_res.status_code == 200
    node = update_exp_res.json()["node"]
    assert node["cycle_traffic_tx"] == 51 * 1024 * 1024

    # 6. 修改节点为双向计费 (traffic_direction="both") 并进行手动校准为 10GB
    update_res = client.put(
        f"/api/monitor/nodes/{node_id}",
        json={
            "traffic_direction": "both",
            "cycle_traffic_calibrate_gb": 10.0,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_node = update_res.json()["node"]
    assert updated_node["traffic_direction"] == "both"
    assert updated_node["cycle_traffic_used_bytes"] == 10 * 1024**3

    # 7. 负数校准值校验：应当被拒绝 (422 Unprocessable Entity)
    bad_calib_res = client.put(
        f"/api/monitor/nodes/{node_id}",
        json={"cycle_traffic_calibrate_gb": -5.0},
        headers=headers,
    )
    assert bad_calib_res.status_code == 422

    # 8. 机器真重启保护：uptime 明显变小 (从 1020 变为 10)
    # 重启后网卡计数重新从 0 累计，当前上报 10MB tx, 20MB rx
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 5.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 10 * 1024 * 1024,
            "net_rx_total": 20 * 1024 * 1024,
            "uptime_seconds": 10,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    # 重启后下一次心跳：增加 5MB tx, 5MB rx, uptime=20
    res = client.post(
        "/api/monitor/report",
        json={
            "cpu_percent": 5.0,
            "ram_total_bytes": 1024**3,
            "ram_used_bytes": 512**3,
            "disk_total_bytes": 20 * 1024**3,
            "disk_used_bytes": 5 * 1024**3,
            "net_tx_total": 15 * 1024 * 1024,
            "net_rx_total": 25 * 1024 * 1024,
            "uptime_seconds": 20,
        },
        headers=agent_headers,
    )
    assert res.status_code == 200

    get_res = client.get("/api/monitor/nodes", headers=headers)
    node = next(n for n in get_res.json()["nodes"] if n["id"] == node_id)
    # 周期用量：校准的 10GB + 重启后的 40MB (15MB tx + 25MB rx)
    expected_bytes = (10 * 1024**3) + (40 * 1024 * 1024)
    assert node["cycle_traffic_used_bytes"] == expected_bytes
