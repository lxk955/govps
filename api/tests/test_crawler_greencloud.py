"""GreenCloud 爬虫：只收录 CN Premium，库存认 Available 数量，规格缺一不可。"""

from decimal import Decimal
from pathlib import Path

import httpx

from app.crawler.greencloud import (
    GreenCloudCrawler,
    PRESET_GREENCLOUD_PRODUCTS,
    parse_greencloud_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "greencloud" / "cn-premium.html"


def _client_with_store(html: str | None = None, status: int = 200) -> httpx.Client:
    body = html if html is not None else FIXTURE.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if "cn-premium-optimized" in str(request.url):
            return httpx.Response(status, text=body)
        return httpx.Response(500, text="offline")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_all_ten_cn_premium_plans():
    products = parse_greencloud_page(FIXTURE.read_text(encoding="utf-8"))
    assert len(products) == 10
    by_id = {p.external_id: p for p in products}

    mini = by_id["2213"]
    assert mini.name == "CN Premium Optimized Plan Mini (Tokyo)"
    assert mini.price == Decimal("25.00")
    assert mini.currency == "USD"
    assert mini.billing_cycle == "monthly"
    assert mini.cpu_cores == 1
    assert mini.ram_gb == Decimal("2")
    assert mini.disk_gb == 20
    assert mini.bandwidth_gb == 500
    assert mini.port_mbps == 500
    assert mini.location == "东京"
    assert mini.line_tags == ["CN2 GIA", "9929", "CMIN2"]
    assert mini.in_stock is False  # 0 Available
    assert mini.stock_verified is True
    assert mini.purchase_url.endswith("pid=2213")

    p2 = by_id["2079"]
    assert p2.port_mbps == 1500  # 1.5Gbps 不能截成 1Gbps
    assert p2.bandwidth_gb == 2000
    assert p2.in_stock is True

    sg = by_id["2305"]
    assert sg.location == "新加坡"
    assert sg.line_tags == ["CN2 GIA", "9929", "CMI"]
    assert "CMIN2" not in sg.line_tags
    assert sg.in_stock is True


def test_zero_available_is_out_of_stock_even_with_order_button():
    html = FIXTURE.read_text(encoding="utf-8")
    products = parse_greencloud_page(html)
    oos = [p for p in products if p.external_id == "2213"][0]
    instock = [p for p in products if p.external_id == "2077"][0]
    assert oos.in_stock is False
    assert instock.in_stock is True


def test_changed_layout_yields_zero():
    html = FIXTURE.read_text(encoding="utf-8").replace("div.product", "div.offer").replace(
        'class="product clearfix"', 'class="offer-box"'
    )
    html = html.replace('id="product', 'id="sku')
    assert parse_greencloud_page(html) == []


def test_incomplete_card_without_ram_is_dropped():
    html = FIXTURE.read_text(encoding="utf-8")
    html = html.replace('<span class="feature-value">2GB</span>', '<span class="feature-value"></span>', 1)
    products = parse_greencloud_page(html)
    assert "2213" not in {p.external_id for p in products}
    assert len(products) == 9


def test_fetch_live_fixture():
    crawler = GreenCloudCrawler()
    products = crawler.fetch(_client_with_store())
    assert len(products) == 10
    assert all(not p.from_preset for p in products)


def test_fetch_http_error_falls_back_to_unverified_presets():
    crawler = GreenCloudCrawler()
    products = crawler.fetch(_client_with_store(status=500))
    assert len(products) == len(PRESET_GREENCLOUD_PRODUCTS)
    assert all(p.from_preset and not p.stock_verified for p in products)
    assert all(p.in_stock is False for p in products)


def test_preset_line_tags_tokyo_vs_singapore():
    by_id = {p.external_id: p for p in PRESET_GREENCLOUD_PRODUCTS}
    assert by_id["2213"].line_tags == ["CN2 GIA", "9929", "CMIN2"]
    assert by_id["2305"].line_tags == ["CN2 GIA", "9929", "CMI"]
