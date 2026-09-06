"""GoMami 爬虫 fixtures 回放与回退测试：录制响应经 MockTransport 注入，测试全程禁网。

fixture: tests/fixtures/gomami/store-turin.html (录制自 gomami.io/store/hkg-turin)
"""

from decimal import Decimal
from pathlib import Path

import httpx

from app.crawler.gomami import GomamiCrawler, parse_gomami_page, PRESET_GOMAMI_PRODUCTS

FIXTURE_TURIN = Path(__file__).parent / "fixtures" / "gomami" / "store-turin.html"


def _client_with_turin_fixture() -> httpx.Client:
    html = FIXTURE_TURIN.read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "hkg-turin" in url:
            return httpx.Response(200, text=html)
        return httpx.Response(500, text="offline")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parse_gomami_page_from_fixture():
    html = FIXTURE_TURIN.read_text(encoding="utf-8")
    products = parse_gomami_page(html, "香港", ["CN2 GIA", "9929", "CMIN2"])
    assert len(products) == 4

    p_map = {p.external_id: p for p in products}
    assert "14" in p_map
    assert "15" in p_map
    assert "16" in p_map
    assert "22" in p_map

    # 验证 HKG Turin Mini
    mini = p_map["14"]
    assert "Mini" in mini.name
    assert mini.price == Decimal("69.00")
    assert mini.currency == "USD"
    assert mini.billing_cycle == "monthly"
    assert mini.cpu_cores == 2
    assert mini.ram_gb == Decimal("4")
    assert mini.disk_gb == 100
    assert mini.bandwidth_gb == 1000
    assert mini.port_mbps == 2000
    assert mini.location == "香港"
    assert mini.line_tags == ["CN2 GIA", "9929", "CMIN2"]
    assert mini.in_stock is True

    # 验证 HKG Turin Ultra
    ultra = p_map["22"]
    assert "Ultra" in ultra.name
    assert ultra.price == Decimal("599.00")
    assert ultra.cpu_cores == 12
    assert ultra.ram_gb == Decimal("32")
    assert ultra.disk_gb == 220
    assert ultra.bandwidth_gb == 10000
    assert ultra.port_mbps == 5000
    assert ultra.in_stock is True


def test_fetch_graceful_fallback_when_http_500():
    """网络故障或盾拦截（HTTP 500）时，优雅回退到预置目录，保证系统不中断。"""
    failing_client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(500)))
    crawler = GomamiCrawler()
    products = crawler.fetch(failing_client)

    assert len(products) == len(PRESET_GOMAMI_PRODUCTS)
    assert len(products) >= 25
    for p in products:
        assert p.price > 0
        assert p.location in ("香港", "日本东京", "美国洛杉矶", "新加坡")
        assert "CN2 GIA" in p.line_tags


def test_preset_products_stock_accuracy():
    """预置数据中，已售罄/下架方案必须准确标记为缺货，不可误标在售。"""
    p_map = {p.external_id: p for p in PRESET_GOMAMI_PRODUCTS}
    # Forge 独服当前官网已售罄
    assert p_map["9"].in_stock is False
    assert p_map["20"].in_stock is False
    # Peak 系列已下架
    assert p_map["1"].in_stock is False
    assert p_map["2"].in_stock is False
    assert p_map["3"].in_stock is False
    # 常规 Turin 与 Pulse 在售
    assert p_map["14"].in_stock is True
    assert p_map["27"].in_stock is True
