from decimal import Decimal
from app.config import settings
from app.crawler.base import make_client, UA, _HAS_CURL_CFFI
from app.crawler.vps import _tier_name, _parse_card
from selectolax.parser import HTMLParser


def test_make_client_default():
    client = make_client(timeout=5.0)
    assert client is not None
    if _HAS_CURL_CFFI:
        assert "Chrome/146" in UA
    else:
        assert "Chrome/146" in client.headers.get("user-agent", "")


def test_make_client_explicit_proxy():
    proxy_url = "http://127.0.0.1:18888"
    client = make_client(timeout=5.0, proxy=proxy_url)
    if _HAS_CURL_CFFI:
        assert client.proxies.get("all") == proxy_url
    else:
        assert any(proxy_url in str(m) for m in client._mounts.values())


def test_make_client_settings_proxy():
    proxy_url = "http://127.0.0.1:19999"
    original_proxy = settings.CRAWLER_PROXY
    try:
        settings.CRAWLER_PROXY = proxy_url
        client = make_client(timeout=5.0)
        if _HAS_CURL_CFFI:
            assert client.proxies.get("all") == proxy_url
        else:
            assert any(proxy_url in str(m) for m in client._mounts.values())
    finally:
        settings.CRAWLER_PROXY = original_proxy


def test_vps_tier_name_cleaning():
    assert _tier_name("Starter") == "入门 Starter"
    assert _tier_name("Essential") == "基础 Essential"
    assert _tier_name("Tokyo EPYC Flash Gen 2") == "EPYC Flash Gen 2"
    assert _tier_name("Singapore EPYC Explorer") == "EPYC Explorer"
    assert _tier_name("Edge Green") == "轻量 Edge Green"


def test_vps_parse_card_singapore():
    card_html = """
    <div class="card cart-product" data-value="250">
      <h4>Singapore Edge Green</h4>
      <span class="product-price cycle-m">€15.95 EUR</span>
      <div><span class="text-muted">CPU</span><span class="font-weight-bold">1 vCore</span></div>
      <div><span class="text-muted">Memory</span><span class="font-weight-bold">2 GB</span></div>
      <div><span class="text-muted">Storage</span><span class="font-weight-bold">20 GB NVMe</span></div>
      <div><span class="text-muted">Transfer</span><span class="font-weight-bold">1 TB</span></div>
    </div>
    """
    card = HTMLParser(card_html).css_first(".cart-product")
    p = _parse_card(card, "新加坡", ["普通BGP"], 1000)
    assert p is not None
    assert p.external_id == "250"
    assert p.name == "SIN 轻量 Edge Green"
    assert p.price == Decimal("15.95")
    assert p.currency == "EUR"
    assert p.billing_cycle == "monthly"
    assert p.in_stock is True
    assert p.from_preset is False
    assert p.stock_verified is True
    assert p.location == "新加坡"
