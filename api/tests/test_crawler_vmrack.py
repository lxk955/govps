"""VMRack 爬虫测试集。"""

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.crawler.base import RawProduct
from app.crawler.vmrack import (
    VMRackCrawler,
    PRESET_VMRACK_PRODUCTS,
    parse_vmrack_api_response,
    _fetch_dvps_fallback,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "vmrack" / "compute_search.json"


@pytest.fixture
def compute_search_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_parse_vmrack_api_response_count_and_specs(compute_search_data):
    products = parse_vmrack_api_response(compute_search_data)
    assert len(products) == 37

    by_name = {p.name: p for p in products}

    # 1. 验证 L1 系列 (Global BGP)
    assert "L1.VPS.2C4G.Base" in by_name
    l1 = by_name["L1.VPS.2C4G.Base"]
    assert l1.external_id == "2572711621899999286"
    assert l1.price == Decimal("5.66")
    assert l1.cpu_cores == 2
    assert l1.ram_gb == Decimal("4")
    assert l1.disk_gb == 60
    assert l1.bandwidth_gb == 4000
    assert l1.port_mbps == 5000
    assert l1.location == "洛杉矶"
    assert l1.line_tags == ["普通BGP"]
    assert l1.in_stock is True

    # 2. 验证 L2 系列 (三网优化 Platinum: CMI / 10099 / 163)
    assert "L2.VPS.2C4G.Base" in by_name
    l2 = by_name["L2.VPS.2C4G.Base"]
    assert l2.external_id == "9190505798939324334"
    assert l2.price == Decimal("8.88")
    assert l2.cpu_cores == 2
    assert l2.ram_gb == Decimal("4")
    assert l2.disk_gb == 60
    assert l2.bandwidth_gb == 4000
    assert l2.port_mbps == 5000
    assert set(l2.line_tags) == {"CMI", "普通BGP"}
    assert l2.in_stock is True

    # 3. 验证 L3 系列 (三网精品 Premium: CN2 GIA / 9929 / CMIN2)
    assert "L3.VPS.2C2G.Base" in by_name
    l3 = by_name["L3.VPS.2C2G.Base"]
    assert l3.external_id == "1106671370188800515"
    assert l3.price == Decimal("13.99")
    assert l3.cpu_cores == 2
    assert l3.ram_gb == Decimal("2")
    assert l3.disk_gb == 40
    assert l3.bandwidth_gb == 1500
    assert l3.port_mbps == 500
    assert set(l3.line_tags) == {"CN2 GIA", "9929", "CMIN2"}
    assert l3.in_stock is True

    # 4. 验证缺货状态 (L3.VPS.DC2.2C2G.Base stock_status=3)
    assert "L3.VPS.DC2.2C2G.Base" in by_name
    l3_oos = by_name["L3.VPS.DC2.2C2G.Base"]
    assert l3_oos.external_id == "7452479152045348950"
    assert l3_oos.in_stock is False

    # 5. 验证不限流量 BVPS (traffic == -1)
    assert "L1.BVPS.DC1.2C2G.Base" in by_name
    bvps = by_name["L1.BVPS.DC1.2C2G.Base"]
    assert bvps.bandwidth_gb == -1
    assert bvps.port_mbps == 100
    assert bvps.in_stock is True


def test_vmrack_crawler_fetch_with_mock_client(compute_search_data):
    crawler = VMRackCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        if "compute/search" in str(request.url):
            return httpx.Response(200, json=compute_search_data)
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    products = crawler.fetch(client)
    assert len(products) == 42


def test_vmrack_crawler_fallback_to_dvps():
    crawler = VMRackCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    fake_dvps_prods = [
        RawProduct(
            external_id=str(i),
            name=f"L1.VPS.{i}C.Base",
            price=Decimal("10.00"),
            currency="USD",
            billing_cycle="monthly",
            in_stock=True,
            location="洛杉矶",
            cpu_cores=1,
            ram_gb=Decimal("1"),
            disk_gb=10,
        )
        for i in range(1, 15)
    ]

    with patch("app.crawler.dvps_source.DvpsSource.fetch_products", return_value=fake_dvps_prods):
        products = crawler.fetch(client)
        assert len(products) == 14
        assert products[0].in_stock is True


def test_vmrack_crawler_fallback_to_presets():
    crawler = VMRackCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with patch("app.crawler.dvps_source.DvpsSource.fetch_products", return_value=[]):
        products = crawler.fetch(client)
        assert len(products) == len(PRESET_VMRACK_PRODUCTS)
        assert all(p.from_preset for p in products)
