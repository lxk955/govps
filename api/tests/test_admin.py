"""管理后台鉴权与概览/配置。"""

from datetime import datetime, timedelta, timezone

from app.models import AffClick, Merchant, PageView, Product, User


def _login(client, db, monkeypatch, email="admin@example.com") -> str:
    monkeypatch.setattr("app.routers.auth.send_email", lambda *a, **k: (True, None))
    client.post("/api/auth/request-code", json={"email": email})
    rec = db.query(__import__("app.models", fromlist=["EmailCode"]).EmailCode).filter_by(email=email).first()
    resp = client.post("/api/auth/verify", json={"email": email, "code": rec.code})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_hardcoded_owner_email_is_admin(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "")
    token = _login(client, db, monkeypatch, "lxk955@gmail.com")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["is_admin"] is True
    ov = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert ov.status_code == 200


def test_me_is_admin_flag(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch, "admin@example.com")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["is_admin"] is True

    other = _login(client, db, monkeypatch, "user@example.com")
    me2 = client.get("/api/auth/me", headers={"Authorization": f"Bearer {other}"})
    assert me2.json()["is_admin"] is False


def test_admin_overview_forbidden_for_normal_user(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch, "user@example.com")
    resp = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_overview_and_settings(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}

    now = datetime.now(timezone.utc)
    m = Merchant(slug="shop", name="Shop", website="https://s.example", enabled=True)
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="1",
        name="Plan",
        price=9,
        purchase_url="https://s.example/buy",
        in_stock=True,
    )
    db.add(p)
    db.flush()
    db.add(PageView(route="/", path="/", session_id="s1", created_at=now))
    db.add(PageView(route="/deals", path="/deals", session_id="s1", created_at=now))
    db.add(PageView(route="/", path="/", session_id="s2", created_at=now - timedelta(days=3)))
    db.add(AffClick(product_id=p.id, src="card", created_at=now))
    db.commit()

    ov = client.get("/api/admin/overview", headers=h)
    assert ov.status_code == 200
    body = ov.json()
    assert body["visits"]["today_pv"] >= 2
    assert body["visits"]["today_uv"] >= 1
    assert body["activity"]["dau"] >= 1
    assert body["activity"]["mau"] >= 1
    assert body["users"]["total"] >= 1
    assert body["aff"]["today"] >= 1
    assert body["aff"]["by_merchant"][0]["slug"] == "shop"
    assert len(body["daily"]) == 30

    merchants = client.get("/api/admin/merchants", headers=h)
    assert merchants.status_code == 200
    row = next(x for x in merchants.json()["merchants"] if x["slug"] == "shop")
    assert row["enabled"] is True
    assert row["in_stock"] == 1

    patched = client.patch(
        "/api/admin/merchants/shop",
        json={"enabled": False, "crawl_interval_minutes": 15},
        headers=h,
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False
    assert patched.json()["crawl_interval_minutes"] == 15
    db.refresh(m)
    assert m.enabled is False
    assert m.crawl_interval_minutes == 15

    saved = client.put(
        "/api/admin/settings",
        json={"daily_mail_cap": 3, "indexnow_enabled": False, "event_dedup_minutes": 60},
        headers=h,
    )
    assert saved.status_code == 200
    assert saved.json()["daily_mail_cap"] == 3
    assert saved.json()["indexnow_enabled"] is False
    assert saved.json()["event_dedup_minutes"] == 60
