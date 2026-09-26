"""VPS 到期提醒功能与配置接口自动化测试。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.main import app
from app.models import ExchangeRate, User, UserNode
from app.services.notifications.expiration_checker import (
    check_expiring_nodes,
    render_expiration_email,
    send_test_expiration_email,
)


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
        user = db.scalar(select(User).where(User.email == "expire_user@example.com"))
        if not user:
            user = User(
                email="expire_user@example.com",
                api_token="test_expire_token_12345",
                view_mode="card",
                currency_mode="CNY",
                monitor_public_enabled=False,
                monitor_expire_notify_enabled=True,
                monitor_expire_stages=[15, 7, 3, 1],
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user


def test_monitor_settings_api(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    # 1. 获取全局设置
    res = client.get("/api/monitor/settings", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["expire_notify_enabled"] is True
    assert data["expire_notify_stages"] == [15, 7, 3, 1]
    assert data["email"] == "expire_user@example.com"
    assert len(data["channels"]) >= 1
    assert data["channels"][0]["id"] == "email"

    # 2. 更新设置
    update_payload = {
        "expire_notify_enabled": False,
        "expire_notify_stages": [7, 1],
    }
    put_res = client.put("/api/monitor/settings", json=update_payload, headers=headers)
    assert put_res.status_code == 200
    new_data = put_res.json()
    assert new_data["expire_notify_enabled"] is False
    assert new_data["expire_notify_stages"] == [7, 1]

    # 3. 恢复设置
    client.put(
        "/api/monitor/settings",
        json={"expire_notify_enabled": True, "expire_notify_stages": [15, 7, 3, 1]},
        headers=headers,
    )


def test_node_expiration_fields_and_reset(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}
    now = datetime.now(timezone.utc)

    # 1. 创建带有到期时间和自定义阶段的节点
    exp1 = (now + timedelta(days=20)).isoformat()
    create_payload = {
        "name": "待测到期机器",
        "country": "hk",
        "group_name": "主力",
        "price": 50.0,
        "currency": "USD",
        "billing_cycle": "monthly",
        "expires_at": exp1,
        "expire_notify_enabled": True,
        "expire_notify_stages": [15, 7, 1],
    }
    create_res = client.post("/api/monitor/nodes", json=create_payload, headers=headers)
    assert create_res.status_code == 200
    node = create_res.json()["node"]
    node_id = node["id"]
    assert node["expire_notify_enabled"] is True
    assert node["expire_notify_stages"] == [15, 7, 1]
    assert node["notified_expire_stages"] == []

    # 2. 模拟巡检触发了 15 天提醒
    with Session(engine) as db:
        db_node = db.get(UserNode, node_id)
        db_node.notified_expire_stages = [15]
        db.commit()

    # 验证列表中显示已通知阶段
    list_res = client.get("/api/monitor/nodes", headers=headers)
    target = next(n for n in list_res.json()["nodes"] if n["id"] == node_id)
    assert target["notified_expire_stages"] == [15]

    # 3. 用户更新了到期时间（例如续费成功延后 30 天），已通知阶段应自动清空
    exp2 = (now + timedelta(days=50)).isoformat()
    put_res = client.put(
        f"/api/monitor/nodes/{node_id}",
        json={"expires_at": exp2},
        headers=headers,
    )
    assert put_res.status_code == 200
    updated_node = put_res.json()["node"]
    assert updated_node["notified_expire_stages"] == []

    # 清理
    client.delete(f"/api/monitor/nodes/{node_id}", headers=headers)


def test_expiration_checker_service(test_user):
    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        # 创建一个 5 天后到期的节点，处于 7 天提醒阈值内
        node = UserNode(
            user_id=test_user.id,
            token="test_checker_token_abc",
            name="即将到期服务器",
            country="us",
            expires_at=now + timedelta(days=5),
            expire_notify_enabled=True,
            expire_notify_stages=[15, 7, 3, 1],
            notified_expire_stages=[],
            is_demo=False,
            is_online=True,
        )
        db.add(node)
        db.commit()
        db.refresh(node)
        node_id = node.id

    with Session(engine) as db:
        # Mock send_email 拦截真实 HTTP 调用
        with patch("app.services.notifications.email_channel.send_email", return_value=(True, None)) as mock_send:
            res = check_expiring_nodes(db)
            assert res["notified"] >= 1
            mock_send.assert_called_once()
            # 验证邮件标题包含节点名和到期提醒
            call_args = mock_send.call_args[1]
            assert "即将到期服务器" in call_args["subject"]
            assert call_args["to"] == test_user.email

        # 验证数据库中已记下 7 天及更早阶段（15天、7天）
        db_node = db.get(UserNode, node_id)
        assert 7 in db_node.notified_expire_stages
        assert 15 in db_node.notified_expire_stages

        # 再次执行巡检，不应重复触发通知
        with patch("app.services.notifications.email_channel.send_email") as mock_send_again:
            res2 = check_expiring_nodes(db)
            mock_send_again.assert_not_called()

        # 清理节点
        db.delete(db_node)
        db.commit()


def test_send_test_expiration_email(client, test_user):
    headers = {"Authorization": f"Bearer {test_user.api_token}"}

    with patch("app.services.notifications.email_channel.send_email", return_value=(True, None)) as mock_send:
        res = client.post("/api/monitor/notify/test", headers=headers)
        assert res.status_code == 200
        assert res.json()["ok"] is True
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert "测试" in call_kwargs["subject"]
        assert call_kwargs["to"] == test_user.email
