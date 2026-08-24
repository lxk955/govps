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
