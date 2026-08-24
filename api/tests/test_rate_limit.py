"""P7 #10：IP 限流 DB 滑动窗口计数测试。

旧实现为进程内 deque（多 worker/重启即失效），现迁移到 request_rate_events 表。
断言语义与旧版一致：先判后记，窗口内第 max+1 次起超限；跨会话（模拟重启）窗口连续。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.models import RequestRateEvent
from app.services.rate_limit import hit_rate_limited


def _seed_hit(db, ip: str, *, minutes_ago: float) -> None:
    db.add(
        RequestRateEvent(ip=ip)
    )
    db.flush()
    # 直接改写 created_at 以构造历史窗口内的命中
    row = db.scalars(
        select(RequestRateEvent).order_by(RequestRateEvent.id.desc())
    ).first()
    row.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    db.commit()


def test_allows_up_to_max_then_limits(db):
    for i in range(5):  # IP_MAX_REQUESTS
        assert hit_rate_limited(db, "1.2.3.4", window_seconds=60, max_requests=5) is False
    assert hit_rate_limited(db, "1.2.3.4", window_seconds=60, max_requests=5) is True
    assert hit_rate_limited(db, "1.2.3.4", window_seconds=60, max_requests=5) is True


def test_windows_are_per_ip(db):
    for _ in range(5):
        hit_rate_limited(db, "5.6.7.8", window_seconds=60, max_requests=5)
    assert hit_rate_limited(db, "5.6.7.8", window_seconds=60, max_requests=5) is True
    # 另一个 IP 不受影响
    assert hit_rate_limited(db, "9.9.9.9", window_seconds=60, max_requests=5) is False


def test_old_hits_fall_out_of_window(db):
    _seed_hit(db, "old-ip", minutes_ago=2)   # 窗口 60s 外
    for _ in range(4):
        assert hit_rate_limited(db, "old-ip", window_seconds=60, max_requests=5) is False
    # 第 5 次仍在窗口内 → 允许；第 6 次超限（旧行不计入）
    assert hit_rate_limited(db, "old-ip", window_seconds=60, max_requests=5) is False
    assert hit_rate_limited(db, "old-ip", window_seconds=60, max_requests=5) is True


def test_window_survives_new_session_like_restart(db):
    """重启等价场景：同一 IP 的历史命中落库后，新 session（新进程视角）仍计入窗口。"""
    ip = "restart-ip"
    for _ in range(5):
        hit_rate_limited(db, ip, window_seconds=60, max_requests=5)
    db.close()

    from app.database import SessionLocal

    with SessionLocal() as fresh:
        assert hit_rate_limited(fresh, ip, window_seconds=60, max_requests=5) is True


def test_auth_endpoint_integrates_db_limiter(client, db):
    """request-code 路由走 DB 计数：同 IP 第 6 次起 429，且事件已落库可审计。
    每次换邮箱以绕开 60s 邮箱级冷却，只考察 IP 维度。"""
    for i in range(5):
        r = client.post("/api/auth/request-code", json={"email": f"rl{i}@example.com"})
        assert r.status_code == 200
    r = client.post("/api/auth/request-code", json={"email": "rl-x@example.com"})
    assert r.status_code == 429
    assert "频繁" in r.json()["detail"]

    rows = db.scalars(select(RequestRateEvent).where(RequestRateEvent.ip == "testclient")).all()
    # 先判后记：5 次放行各留一行，超限请求不追加
    assert len(rows) == 5
