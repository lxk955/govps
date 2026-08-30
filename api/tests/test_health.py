def test_health_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_products_shape(client, db):
    resp = client.get("/api/products")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body and "items" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


def test_stock_endpoints_no_store(client):
    # 详情 404 仍走 /api/products/*，不触发列表的 concat 分组
    health = client.get("/api/health")
    missing = client.get("/api/products/999999")
    assert health.headers.get("cache-control") == "no-store"
    assert missing.status_code == 404
    assert missing.headers.get("cache-control") == "no-store"


def test_non_realtime_gets_allow_short_cache(client):
    summary = client.get("/api/events/summary").headers.get("cache-control", "")
    rates = client.get("/api/rates").headers.get("cache-control", "")
    snaps = client.get("/api/rates/snapshots").headers.get("cache-control", "")
    assert "max-age=60" in summary
    assert "max-age=300" in rates
    assert "max-age=300" in snaps
    from app.main import _API_CACHE_GET
    assert "/api/products/merchants" in _API_CACHE_GET