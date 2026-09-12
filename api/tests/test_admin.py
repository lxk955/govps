"""管理后台鉴权与概览/配置。"""

from datetime import datetime, timedelta, timezone

from app.models import AffClick, CrawlLog, Merchant, PageView, Product, User, Watchlist


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
    assert row["aff_status"] == "direct"
    assert row["aff_clicks_d30"] >= 1

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


def test_admin_crawler_logs(client, db, monkeypatch):
    from app.models import CrawlLog

    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}

    log = CrawlLog(
        merchant_name="DMIT",
        merchant_slug="dmit",
        status="success",
        method="官方 WHMCS 订购页 + FlareSolverr 求解",
        products_count=105,
        official_count=105,
        in_stock_count=18,
        duration_ms=2500,
        message="100% 官方一手，抓取 105 款，18 款在售",
    )
    db.add(log)
    db.commit()

    resp = client.get("/api/admin/crawler/logs", headers=h)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["logs"]) >= 1
    assert data["logs"][0]["merchant_slug"] == "dmit"
    assert data["logs"][0]["status"] == "success"
    assert data["logs"][0]["method"] == "官方 WHMCS 订购页 + FlareSolverr 求解"
    assert data["logs"][0]["products_count"] == 105
    assert len(data["latest_by_merchant"]) >= 1
    assert data["latest_by_merchant"][0]["merchant_slug"] == "dmit"


def test_admin_users_list_and_detail(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch, "admin@example.com")
    h = {"Authorization": f"Bearer {token}"}
    other_token = _login(client, db, monkeypatch, "alice@example.com")

    now = datetime.now(timezone.utc)
    m = Merchant(slug="shop", name="Shop", website="https://s.example", enabled=True)
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="1",
        name="Tokyo Mini",
        price=9,
        purchase_url="https://s.example/buy",
        in_stock=True,
    )
    db.add(p)
    db.flush()
    alice = db.query(User).filter_by(email="alice@example.com").first()
    db.add(Watchlist(user_id=alice.id, product_id=p.id, notify_restock=True, notify_price_drop=False))
    db.add(PageView(route="/", path="/", session_id="s1", user_id=alice.id, created_at=now))
    db.commit()

    forbidden = client.get("/api/admin/users", headers={"Authorization": f"Bearer {other_token}"})
    assert forbidden.status_code == 403

    listing = client.get("/api/admin/users", headers=h)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 2
    emails = {u["email"] for u in body["users"]}
    assert "alice@example.com" in emails
    assert "api_token" not in body["users"][0]
    alice_row = next(u for u in body["users"] if u["email"] == "alice@example.com")
    assert alice_row["watch_count"] == 1
    assert alice_row["last_seen_at"] is not None

    found = client.get("/api/admin/users?q=alice", headers=h)
    assert found.status_code == 200
    assert found.json()["total"] == 1
    assert found.json()["users"][0]["email"] == "alice@example.com"

    detail = client.get(f"/api/admin/users/{alice.id}", headers=h)
    assert detail.status_code == 200
    d = detail.json()
    assert d["user"]["email"] == "alice@example.com"
    assert "api_token" not in d["user"]
    assert d["user"]["watch_count"] == 1
    assert d["user"]["pageviews"] == 1
    assert d["watchlist"][0]["name"] == "Tokyo Mini"
    assert d["watchlist"][0]["merchant"] == "Shop"
    assert d["recent_views"][0]["path"] == "/"

    missing = client.get("/api/admin/users/999999", headers=h)
    assert missing.status_code == 404


def test_admin_aff_template_and_scan_does_not_overwrite(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}

    m = Merchant(slug="dmit", name="DMIT", website="https://www.dmit.io", enabled=True)
    db.add(m)
    db.commit()

    bad = client.patch(
        "/api/admin/merchants/dmit",
        json={"aff_url_template": "javascript:alert(1)"},
        headers=h,
    )
    assert bad.status_code == 400

    saved = client.patch(
        "/api/admin/merchants/dmit",
        json={"aff_url_template": "https://www.dmit.io/aff.php?aff=1&pid={pid}"},
        headers=h,
    )
    assert saved.status_code == 200
    assert saved.json()["aff_status"] == "active"
    assert "aff=1" in saved.json()["aff_url_template"]

    from app.services.scan import ensure_merchants

    ensure_merchants(db)
    db.commit()
    db.refresh(m)
    assert m.aff_url_template == "https://www.dmit.io/aff.php?aff=1&pid={pid}"

    restored = client.patch(
        "/api/admin/merchants/dmit",
        json={"restore_aff_default": True},
        headers=h,
    )
    assert restored.status_code == 200
    assert restored.json()["aff_code_default"]
    assert restored.json()["aff_url_template"] == restored.json()["aff_code_default"]


def test_admin_crawler_logs_and_settings_resilient(client, db, monkeypatch):
    monkeypatch.setattr("app.config.settings.ADMIN_EMAILS", "admin@example.com")
    token = _login(client, db, monkeypatch)
    h = {"Authorization": f"Bearer {token}"}

    # Settings returns defaults even if table query fails
    res = client.get("/api/admin/settings", headers=h)
    assert res.status_code == 200
    assert "event_dedup_minutes" in res.json()

    # Crawler logs returns empty list if query fails or table is empty
    logs = client.get("/api/admin/crawler/logs", headers=h)
    assert logs.status_code == 200
    assert "logs" in logs.json()
    assert "latest_by_merchant" in logs.json()

