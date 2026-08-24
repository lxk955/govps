"""P4 认证与关注域测试（mock 发信，与真实邮件链路验证明确区分）。

覆盖：验证码有效期/单次有效/尝试上限/发送冷却/IP 限流、token 轮换、
401 统一行为、关注幂等（PUT upsert 与 DELETE 缺省成功）。
真实 Resend 链路不在本套件内（环境未配置 RESEND_API_KEY）。
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models import EmailCode, Product, User, Watchlist
from app.services.scan import upsert_product
from app.crawler.base import RawProduct

# P7 #10 起 IP 限流迁移到 request_rate_events 表：无进程内状态需要重置，
# 测试隔离由 conftest 的 db fixture（逐用例 drop/create 全部表）保证。


def _request_code(client, monkeypatch, email="u@example.com"):
    monkeypatch.setattr("app.routers.auth.send_email", lambda *a, **k: (True, None))
    return client.post("/api/auth/request-code", json={"email": email})


def _latest_code(db, email="u@example.com") -> str:
    rec = db.query(EmailCode).filter_by(email=email).order_by(EmailCode.id.desc()).first()
    return rec.code


def _login(client, db, monkeypatch, email="u@example.com") -> str:
    _request_code(client, monkeypatch, email)
    code = _latest_code(db, email)
    resp = client.post("/api/auth/verify", json={"email": email, "code": code})
    assert resp.status_code == 200
    return resp.json()["token"]


def _merchant(db):
    m = Merchant_model(slug="shopw", name="ShopW", website="https://w.example")
    db.add(m)
    db.flush()
    return m


Merchant_model = __import__("app.models", fromlist=["Merchant"]).Merchant


# ── 验证码生命周期 ──────────────────────────────────────────────


def test_request_code_resend_cooldown(client, db, monkeypatch):
    _request_code(client, monkeypatch)
    resp2 = client.post("/api/auth/request-code", json={"email": "u@example.com"})
    assert resp2.status_code == 429


def test_request_code_ip_rate_limit(client, db, monkeypatch):
    for i in range(5):
        r = _request_code(client, monkeypatch, email=f"u{i}@example.com")
        assert r.status_code == 200
    sixth = _request_code(client, monkeypatch, email="u9@example.com")
    assert sixth.status_code == 429


def test_verify_rejects_wrong_then_locks_after_max_attempts(client, db, monkeypatch):
    _request_code(client, monkeypatch)
    real = _latest_code(db)
    for attempt in range(5):
        wrong = "000000" if real != "000000" else "111111"
        r = client.post("/api/auth/verify", json={"email": "u@example.com", "code": wrong})
        assert r.status_code == 400
    # 第 6 次：即使拿对验证码也已被锁定，需重新获取
    r = client.post("/api/auth/verify", json={"email": "u@example.com", "code": real})
    assert r.status_code == 400
    assert "重新获取" in r.json()["detail"]


def test_verify_expired_code_rejected(client, db, monkeypatch):
    _request_code(client, monkeypatch)
    rec = db.query(EmailCode).filter_by(email="u@example.com").first()
    rec.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    code = rec.code
    r = client.post("/api/auth/verify", json={"email": "u@example.com", "code": code})
    assert r.status_code == 400
    assert "过期" in r.json()["detail"]


def test_verify_is_single_use(client, db, monkeypatch):
    _request_code(client, monkeypatch)
    code = _latest_code(db)
    first = client.post("/api/auth/verify", json={"email": "u@example.com", "code": code})
    assert first.status_code == 200
    # 同一验证码重放：已删除，不得再次登录
    replay = client.post("/api/auth/verify", json={"email": "u@example.com", "code": code})
    assert replay.status_code == 400


def test_login_rotates_token_and_old_token_dies(client, db, monkeypatch):
    t1 = _login(client, db, monkeypatch)
    t2 = _login(client, db, monkeypatch)
    assert t1 != t2
    me_old = client.get("/api/auth/me", headers={"Authorization": f"Bearer {t1}"})
    me_new = client.get("/api/auth/me", headers={"Authorization": f"Bearer {t2}"})
    assert me_old.status_code == 401
    assert me_new.status_code == 200
    assert me_new.json()["email"] == "u@example.com"


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


# ── 关注域 ──────────────────────────────────────────────────────


def _watch_product(db) -> Product:
    from app.models import Merchant

    m = db.scalar(Merchant.__table__.select().limit(1))
    if m is None:
        m = Merchant(slug="shopw", name="ShopW", website="https://w.example")
        db.add(m)
        db.flush()
    p, _ = upsert_product(
        db, m,
        RawProduct(external_id=f"w-{m.id}", name="Watchable Plan", price=Decimal("10"),
                   currency="USD", billing_cycle="annually",
                   purchase_url="https://w.example/buy", in_stock=True),
    )
    # TestClient 走独立会话：必须提交后端点才可见
    db.commit()
    return p


from decimal import Decimal  # noqa: E402


def test_watch_put_is_idempotent_and_updates_prefs(client, db, monkeypatch):
    token = _login(client, db, monkeypatch)
    p = _watch_product(db)
    h = {"Authorization": f"Bearer {token}"}

    payload = {"notify_restock": True, "notify_price_drop": True, "min_drop_percent": 5}
    r1 = client.put(f"/api/watchlist/{p.id}", json=payload, headers=h)
    r2 = client.put(f"/api/watchlist/{p.id}", json=payload, headers=h)
    assert r1.status_code == r2.status_code == 200
    assert db.query(Watchlist).count() == 1  # 幂等：不产生重复行

    # 更新偏好仍是同一行
    r3 = client.put(f"/api/watchlist/{p.id}",
                    json={"notify_restock": False, "notify_price_drop": True, "min_drop_percent": 0},
                    headers=h)
    assert r3.status_code == 200
    w = db.query(Watchlist).one()
    assert w.notify_restock is False


def test_unwatch_is_idempotent(client, db, monkeypatch):
    token = _login(client, db, monkeypatch)
    p = _watch_product(db)
    h = {"Authorization": f"Bearer {token}"}
    client.put(f"/api/watchlist/{p.id}",
               json={"notify_restock": True, "notify_price_drop": True, "min_drop_percent": 0},
               headers=h)
    d1 = client.delete(f"/api/watchlist/{p.id}", headers=h)
    d2 = client.delete(f"/api/watchlist/{p.id}", headers=h)
    assert d1.json()["watching"] is False
    assert d2.status_code == 200 and d2.json()["watching"] is False
    assert db.query(Watchlist).count() == 0


def test_watch_requires_auth(client, db):
    p = _watch_product(db)
    r = client.put(f"/api/watchlist/{p.id}",
                   json={"notify_restock": True, "notify_price_drop": True, "min_drop_percent": 0})
    assert r.status_code == 401
    assert client.get("/api/watchlist").status_code == 401
    assert client.get(f"/api/watchlist/{p.id}").status_code == 401


def test_watch_status_endpoint(client, db, monkeypatch):
    token = _login(client, db, monkeypatch)
    p = _watch_product(db)
    h = {"Authorization": f"Bearer {token}"}
    before = client.get(f"/api/watchlist/{p.id}", headers=h).json()
    assert before["watching"] is False
    client.put(f"/api/watchlist/{p.id}",
               json={"notify_restock": True, "notify_price_drop": False, "min_drop_percent": 10},
               headers=h)
    after = client.get(f"/api/watchlist/{p.id}", headers=h).json()
    assert after == {"watching": True, "notify_restock": True,
                     "notify_price_drop": False, "min_drop_percent": 10}


def test_watched_filter_401_for_anonymous_and_filters_for_user(client, db, monkeypatch):
    token = _login(client, db, monkeypatch)
    p = _watch_product(db)
    h = {"Authorization": f"Bearer {token}"}
    client.put(f"/api/watchlist/{p.id}",
               json={"notify_restock": True, "notify_price_drop": True, "min_drop_percent": 0},
               headers=h)

    anon = client.get("/api/products", params={"watched": "true"})
    assert anon.status_code == 401

    mine = client.get("/api/products", params={"watched": "true"}, headers=h)
    assert mine.status_code == 200
    assert [x["id"] for x in mine.json()["items"]] == [p.id]


def test_no_code_in_logs_on_mail_failure(client, db, monkeypatch, capsys):
    """邮件发送失败路径不得把验证码写进日志（安全要求）。"""
    monkeypatch.setattr("app.routers.auth.settings.RESEND_API_KEY", "")
    monkeypatch.setattr("app.routers.auth.send_email", lambda *a, **k: (False, "not configured"))
    r = client.post("/api/auth/request-code", json={"email": "dev@example.com"})
    assert r.status_code == 200
    captured = capsys.readouterr()
    dev_code = r.json()["dev_code"]
    assert dev_code not in captured.out
