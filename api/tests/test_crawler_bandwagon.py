"""搬瓦工爬虫 fixtures 回放测试：录制响应经 MockTransport 注入，测试全程禁网。

fixture: tests/fixtures/bandwagon/get-data.json（2026-08-23 录制自 bwh81.net/order/get-data）
"""

import json
from decimal import Decimal
from pathlib import Path

import httpx

from app.crawler.bandwagon import DATA_URL, BandwagonCrawler

FIXTURE = Path(__file__).parent / "fixtures" / "bandwagon" / "get-data.json"


def _client_with_fixture() -> httpx.Client:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    return httpx.Client(transport=transport)


def test_fetch_parses_products_from_recorded_json():
    crawler = BandwagonCrawler()
    products = crawler.fetch(_client_with_fixture())

    assert len(products) >= 20  # 线上目录长期在 40+ 款，回放不应显著缩水
    for p in products:
        assert p.external_id.isdigit()
        assert p.price > 0
        assert isinstance(p.in_stock, bool)
        assert p.purchase_url.startswith("https://bwh81.net/cart.php?a=add&pid=")


def test_fetch_normalizes_periods_and_price_options():
    crawler = BandwagonCrawler()
    products = crawler.fetch(_client_with_fixture())

    with_multi_cycle = [p for p in products if len(p.price_options) > 1]
    assert with_multi_cycle, "录制的目录中应存在多付款周期套餐"
    for p in with_multi_cycle:
        cycles = {o["billing_cycle"] for o in p.price_options}
        assert cycles <= {"monthly", "quarterly", "semi-annually", "annually", "biennially", "triennially"}


def test_fetch_maps_specs_from_official_fields():
    crawler = BandwagonCrawler()
    products = crawler.fetch(_client_with_fixture())

    speced = [p for p in products if p.cpu_cores and p.ram_gb]
    assert speced, "官方 JSON 含 cpu/ram 字段，应至少解析出一批规格"
    p = speced[0]
    assert p.ram_gb > Decimal(0)
    assert p.disk_gb is None or p.disk_gb > 0


def test_out_of_stock_flag_respected():
    crawler = BandwagonCrawler()
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    oos_ids = {str(item["id"]) for item in data.get("products", []) if item.get("outOfStock")}

    products = {p.external_id: p for p in crawler.fetch(_client_with_fixture())}
    for pid in oos_ids & products.keys():
        assert products[pid].in_stock is False, f"官方标记 outOfStock 的 {pid} 不应被判有货"
