"""P0 安全、代理信任链、多币种评分、数据新鲜度与权威 DNS 加固回归测试。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import dns.flags
import dns.message
import dns.rcode
from starlette.requests import Request
from sqlalchemy import func, select

from app.crawler.base import MerchantCrawler, RawProduct
from app.models import AffClick, DnsLeakHit, EmailCode, ExchangeRate, Merchant, PriceSnapshot, Product, User
from app.routers.auth import VERIFY_IP_MAX_REQUESTS
from app.routers.go import _auto_post_page
from app.services import scan as scan_mod
from app.services.client_ip import client_ip
from app.services.dns_server import (
    _clear_recent_hits_cache,
    extract_probe_token,
    handle_dns_packet,
)
from app.services.materialize import refresh_derived_fields
from app.services.scan import run_scan, upsert_product
from app.services.scoring import calculate_scores_and_reasons


def _make_request(peer_ip: str, headers: dict[str, str]) -> Request:
    raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": (peer_ip, 54321),
    }
    return Request(scope)


def test_client_ip_trusts_cf_header_only_from_cloudflare_edge():
    # 1. 流量经 Cloudflare (172.64.10.20) -> Caddy (172.18.0.4) -> API
    req_cf = _make_request(
        "172.18.0.4",
        {
            "X-Real-IP": "172.64.10.20",
            "CF-Connecting-IP": "198.51.100.42",
        },
    )
    assert client_ip(req_cf) == "198.51.100.42"

    # 2. 攻击者绕过 Cloudflare 直连源站 80/443（Caddy 记录真实对端 203.0.113.9），伪造 CF-Connecting-IP 企图绕过限流
    req_spoof = _make_request(
        "172.18.0.4",
        {
            "X-Real-IP": "203.0.113.9",
            "CF-Connecting-IP": "8.8.8.8",
            "X-Forwarded-For": "1.1.1.1, 203.0.113.9",
        },
    )
    assert client_ip(req_spoof) == "203.0.113.9"

    # 3. 公网直接访问 API（无本地反代）：非 Cloudflare 对端一律忽略转发头
    req_direct = _make_request(
        "198.51.100.77",
        {
            "CF-Connecting-IP": "9.9.9.9",
            "X-Real-IP": "4.4.4.4",
        },
    )
    assert client_ip(req_direct) == "198.51.100.77"


def test_go_and_click_record_real_client_ip_and_user_id(client, db):
    m = Merchant(slug="dmit", name="DMIT", website="https://www.dmit.io")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id,
        external_id="101",
        name="LAX Pro",
        price=Decimal("39.90"),
        purchase_url="https://www.dmit.io/cart.php?a=add&pid=101",
        in_stock=True,
    )
    user = User(email="buyer@example.com", api_token="tok_buyer_123")
    db.add_all([p, user])
    db.commit()

    headers = {
        "Authorization": "Bearer tok_buyer_123",
        "X-Real-IP": "172.64.1.2",
        "CF-Connecting-IP": "198.51.100.88",
        "User-Agent": "TestBrowser/1.0",
    }
    r_go = client.get(f"/go/{p.id}", headers=headers, follow_redirects=False)
    assert r_go.status_code == 302

    r_click = client.post(f"/api/products/{p.id}/click", headers=headers)
    assert r_click.status_code == 200

    clicks = db.scalars(select(AffClick).order_by(AffClick.id.asc())).all()
    assert len(clicks) == 2
    assert clicks[0].ip == "198.51.100.88"
    assert clicks[0].user_id == user.id
    assert clicks[1].ip == "198.51.100.88"
    assert clicks[1].user_id == user.id

    html_resp = _auto_post_page('https://example.com/cart" onmouseover="alert(1)', {"id": "1"})
    body = html_resp.body.decode("utf-8")
    assert '" onmouseover="' not in body
    assert "&quot;" in body


def test_cross_currency_scoring_and_materialization(client, db):
    m = Merchant(slug="multicur", name="MultiCur", website="https://multicur.example")
    db.add(m)
    db.flush()
    db.add_all(
        [
            ExchangeRate(code="USD", units_per_usd=Decimal("1.0")),
            ExchangeRate(code="CNY", units_per_usd=Decimal("7.2")),
            ExchangeRate(code="CAD", units_per_usd=Decimal("1.38")),
            ExchangeRate(code="EUR", units_per_usd=Decimal("0.86")),
        ]
    )
    # 1) CNY ¥180/年 ≈ $25 USD <= $36：应命中「超低门槛年付」与「大内存高配」
    p_cny_low, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="cny-low",
            name="HK BGP 2G",
            price=Decimal("180.00"),
            currency="CNY",
            billing_cycle="annually",
            purchase_url="https://multicur.example/1",
            in_stock=True,
            ram_gb=Decimal("2.0"),
        ),
    )
    # 2) CAD CA$48/年 ≈ $34.78 USD <= $36：原币数值 >36，折算 USD 后应命中 <=36 档
    p_cad, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="cad-low",
            name="LAX 1G",
            price=Decimal("48.00"),
            currency="CAD",
            billing_cycle="annually",
            purchase_url="https://multicur.example/2",
            in_stock=True,
            ram_gb=Decimal("1.0"),
        ),
    )
    # 3) EUR €58/年 ≈ $67.44 USD > $60：原币数值 <=60，但折算 USD 后不应误拿 <=60 档与大内存加分
    p_eur, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="eur-mid",
            name="FRA 2G",
            price=Decimal("58.00"),
            currency="EUR",
            billing_cycle="annually",
            purchase_url="https://multicur.example/3",
            in_stock=True,
            ram_gb=Decimal("2.0"),
        ),
    )
    # 4) 未知币种 JPY（无汇率）：绝不按 1:1 假定为美元，且原始价格/币种不被覆盖
    p_jpy, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="jpy-unknown",
            name="TYO 2G",
            price=Decimal("30.00"),
            currency="JPY",
            billing_cycle="annually",
            purchase_url="https://multicur.example/4",
            in_stock=True,
            ram_gb=Decimal("2.0"),
        ),
    )
    db.commit()

    refresh_derived_fields(db)
    db.commit()
    for prod in (p_cny_low, p_cad, p_eur, p_jpy):
        db.refresh(prod)

    assert "超低门槛年付" in (p_cny_low.score_reasons or [])
    assert "大内存高配" in (p_cny_low.score_reasons or [])
    assert Decimal(str(p_cny_low.price)) == Decimal("180.00")
    assert p_cny_low.currency == "CNY"

    assert "超低门槛年付" in (p_cad.score_reasons or [])

    assert "年付高性价比" not in (p_eur.score_reasons or [])
    assert "大内存高配" not in (p_eur.score_reasons or [])

    deal_jpy, _, _, reasons_jpy = calculate_scores_and_reasons(p_jpy, rates={"CNY": 7.2})
    assert "超低门槛年付" not in reasons_jpy
    assert deal_jpy == 30.0  # 仅基础在售分 +30，不误发 USD 低价加分


def test_dns_leak_results_blocks_short_prefix_enumeration(client, db, monkeypatch):
    monkeypatch.setattr("app.routers.ipcheck._lookup_resolver_geo", lambda ip: _async_const("TestISP"))
    db.add_all(
        [
            DnsLeakHit(
                token="victimtoken1234",
                resolver_ip="198.51.100.11",
                query_name="victimtoken12340.dnstest.govps.xyz",
            ),
            DnsLeakHit(
                token="mytoken98765432",
                resolver_ip="203.0.113.22",
                query_name="mytoken987654320.dnstest.govps.xyz",
            ),
        ]
    )
    db.commit()

    # 短前缀或非法字符查询不得枚举出任何他人的 Resolver IP
    for bad in ("v", "victim", "victim*", "bad_token!"):
        r_bad = client.get("/api/ip/dns-leak/results", params={"token": bad})
        assert r_bad.status_code == 200
        assert r_bad.json()["resolvers"] == []

    # 合法完整 token 仅返回自身命中，不串入他人记录
    r_ok = client.get("/api/ip/dns-leak/results", params={"token": "mytoken98765432"})
    assert r_ok.status_code == 200
    ips = [item["resolver"] for item in r_ok.json()["resolvers"]]
    assert ips == ["203.0.113.22"]


async def _async_const(val: str) -> str:
    return val


def test_auth_verify_enforces_per_ip_rate_limit(client, db):
    now = datetime.now(timezone.utc)
    for i in range(VERIFY_IP_MAX_REQUESTS + 2):
        db.add(
            EmailCode(
                email=f"u{i}@example.com",
                code="123456",
                expires_at=now + timedelta(minutes=10),
            )
        )
    db.commit()

    attacker_headers = {"X-Real-IP": "203.0.113.55"}
    for i in range(VERIFY_IP_MAX_REQUESTS):
        resp = client.post(
            "/api/auth/verify",
            headers=attacker_headers,
            json={"email": f"u{i}@example.com", "code": "000000"},
        )
        assert resp.status_code == 400

    blocked = client.post(
        "/api/auth/verify",
        headers=attacker_headers,
        json={"email": f"u{VERIFY_IP_MAX_REQUESTS}@example.com", "code": "123456"},
    )
    assert blocked.status_code == 429

    # 另一正常访客 IP 不受攻击者限流影响
    legit = client.post(
        "/api/auth/verify",
        headers={"X-Real-IP": "198.51.100.66"},
        json={"email": f"u{VERIFY_IP_MAX_REQUESTS + 1}@example.com", "code": "123456"},
    )
    assert legit.status_code == 200
    assert legit.json()["token"]


def test_unverified_preset_preserves_product_and_merchant_freshness(db, monkeypatch):
    m = Merchant(slug="freshshop", name="FreshShop", website="https://fresh.example")
    db.add(m)
    db.flush()

    # 1. 新建未经实时核验的静态预设：last_checked_at 必须为空
    p_preset, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="preset-only",
            name="Preset Plan",
            price=Decimal("49.90"),
            purchase_url="https://fresh.example/p",
            in_stock=False,
            from_preset=True,
            stock_verified=False,
        ),
    )
    assert p_preset.last_checked_at is None

    # 2. 已有实时验证过的套餐，后续降级为静态预设时不得篡改 last_checked_at 与实时价格/快照
    p_live, _ = upsert_product(
        db,
        m,
        RawProduct(
            external_id="live-1",
            name="Live Plan",
            price=Decimal("29.90"),
            purchase_url="https://fresh.example/live",
            in_stock=True,
            from_preset=False,
            stock_verified=True,
        ),
    )
    real_checked_at = datetime.now(timezone.utc) - timedelta(hours=2)
    p_live.last_checked_at = real_checked_at
    db.flush()
    snap_count_before = db.scalar(
        select(func.count(PriceSnapshot.id)).where(PriceSnapshot.product_id == p_live.id)
    )

    upsert_product(
        db,
        m,
        RawProduct(
            external_id="live-1",
            name="Live Plan",
            price=Decimal("59.90"),
            purchase_url="https://fresh.example/live",
            in_stock=False,
            from_preset=True,
            stock_verified=False,
        ),
    )
    db.flush()
    db.refresh(p_live)
    assert p_live.last_checked_at.replace(tzinfo=timezone.utc) == real_checked_at
    assert Decimal(str(p_live.price)) == Decimal("29.90")
    assert p_live.in_stock is True
    snap_count_after = db.scalar(
        select(func.count(PriceSnapshot.id)).where(PriceSnapshot.product_id == p_live.id)
    )
    assert snap_count_after == snap_count_before

    # 3. 整家爬虫 100% 回退到未核验静态预设时，不得推进 merchant.last_success_at
    class _DegradedCrawler(MerchantCrawler):
        slug = "freshshop"
        name = "FreshShop"
        website = "https://fresh.example"

        def fetch(self, client):
            return [
                RawProduct(
                    external_id="live-1",
                    name="Live Plan",
                    price=Decimal("59.90"),
                    purchase_url="https://fresh.example/live",
                    in_stock=False,
                    from_preset=True,
                    stock_verified=False,
                )
            ]

    prev_success = datetime.now(timezone.utc) - timedelta(hours=3)
    m.last_success_at = prev_success
    db.commit()

    monkeypatch.setattr(scan_mod, "CRAWLERS", [_DegradedCrawler()])
    monkeypatch.setattr(scan_mod, "ensure_merchants", lambda _db: None)
    run_scan(db, force=True)
    db.refresh(m)
    assert m.last_success_at.replace(tzinfo=timezone.utc) == prev_success
    assert m.last_error and "预设" in m.last_error


def test_dns_server_refuses_unrelated_domains_and_deduplicates_hits(db):
    _clear_recent_hits_cache()

    # 1. 非本权威域查询必须返回 REFUSED 且不置 AA、不落库
    q_ext = dns.message.make_query("example.com", "A").to_wire()
    raw_ext = handle_dns_packet(q_ext, ("198.51.100.1", 53000))
    assert raw_ext is not None
    resp_ext = dns.message.from_wire(raw_ext)
    assert resp_ext.rcode() == dns.rcode.REFUSED
    assert not (resp_ext.flags & dns.flags.AA)
    assert db.scalar(select(func.count(DnsLeakHit.id))) == 0

    # 2. 裸域与过短非法子域正常应答权威记录，但不写入垃圾命中
    for qname in ("dnstest.govps.xyz", "a.dnstest.govps.xyz", "sub.token12345.dnstest.govps.xyz"):
        assert extract_probe_token(qname) is None
        q_invalid = dns.message.make_query(qname, "A").to_wire()
        raw_inv = handle_dns_packet(q_invalid, ("198.51.100.2", 53000))
        assert raw_inv is not None
    assert db.scalar(select(func.count(DnsLeakHit.id))) == 0

    # 3. 同一 (token, resolver_ip) 的 4 路并发探针去重为单次 SQLite 写入
    for idx in range(4):
        q_probe = dns.message.make_query(f"probetok99{idx}.dnstest.govps.xyz", "A").to_wire()
        raw_probe = handle_dns_packet(q_probe, ("198.51.100.3", 53000))
        assert raw_probe is not None
        resp_probe = dns.message.from_wire(raw_probe)
        assert resp_probe.rcode() == dns.rcode.NOERROR
        assert bool(resp_probe.flags & dns.flags.AA)

    hits = db.scalars(select(DnsLeakHit)).all()
    assert len(hits) == 1
    assert hits[0].token == "probetok99"
    assert hits[0].resolver_ip == "198.51.100.3"
    _clear_recent_hits_cache()
