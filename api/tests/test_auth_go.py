"""Auth OTP leak, /go HTML escape, disabled merchant visibility."""

from decimal import Decimal

from app.models import EventType, Merchant, NotifyEvent, Product
from app.services.notify import render_event_email


def test_request_code_has_no_dev_code_when_mail_configured(client, monkeypatch):
    import app.routers.auth as auth_mod

    monkeypatch.setattr(auth_mod.settings, "RESEND_API_KEY", "re_test_key")
    monkeypatch.setattr(auth_mod, "send_email", lambda *a, **k: (True, None))

    resp = client.post("/api/auth/request-code", json={"email": "user@example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("dev_code") in (None, "")


def test_request_code_dev_code_only_when_mail_unconfigured(client, monkeypatch):
    import app.routers.auth as auth_mod

    monkeypatch.setattr(auth_mod.settings, "RESEND_API_KEY", "")
    monkeypatch.setattr(auth_mod, "send_email", lambda *a, **k: (False, "not configured"))

    resp = client.post("/api/auth/request-code", json={"email": "dev@example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("dev_code")
    assert len(body["dev_code"]) == 6


def test_go_escapes_malicious_purchase_url(client, db):
    m = Merchant(slug="evil", name="Evil", website="https://evil.example")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="9",
        name='Plan <script>alert(1)</script>',
        price=Decimal("1"),
        purchase_url='https://evil.example/buy?q=" onclick="alert(1)',
        in_stock=False,
    )
    db.add(p)
    db.commit()

    resp = client.get(f"/go/{p.id}", follow_redirects=False)
    assert resp.status_code == 200
    html = resp.text
    assert 'q=" onclick="' not in html
    assert "<script>" not in html
    assert "&quot;" in html or "&#34;" in html
    assert "&lt;script&gt;" in html


def test_disabled_merchant_hidden_from_list_and_go(client, db):
    m = Merchant(
        slug="off",
        name="OffCo",
        website="https://off.example",
        enabled=False,
    )
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="1",
        name="Hidden plan",
        price=Decimal("9"),
        purchase_url="https://off.example/buy",
        in_stock=True,
    )
    db.add(p)
    db.commit()

    listed = client.get("/api/products")
    assert listed.status_code == 200
    names = {item["name"] for item in listed.json()["items"]}
    assert "Hidden plan" not in names

    go = client.get(f"/go/{p.id}", follow_redirects=False)
    assert go.status_code == 404


def test_notify_email_escapes_product_and_merchant_names(db):
    m = Merchant(slug="x", name='Shop <img src=x>', website="https://x.example")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="1",
        name='Plan "><script>alert(1)</script>',
        price=Decimal("1"),
        purchase_url="https://x.example/buy",
        in_stock=True,
        location='LA <b>x</b>',
    )
    db.add(p)
    db.flush()
    p.merchant = m
    ev = NotifyEvent(product_id=p.id, type=EventType.RESTOCK.value)
    _subject, html = render_event_email(ev, p)
    assert "<script>" not in html
    assert "<img" not in html
    assert "&lt;img" in html
    assert "&lt;script&gt;" in html
    assert "&quot;" in html or "&#x27;" in html or "&#34;" in html
