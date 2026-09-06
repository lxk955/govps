"""Evoxt 爬虫测试集。"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.crawler.base import RawProduct
from app.crawler.evoxt import (
    EvoxtCrawler,
    PRESET_EVOXT_PRODUCTS,
    parse_evoxt_pricing_page,
    _fetch_dvps_fallback,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "evoxt" / "pricing.html"


@pytest.fixture
def pricing_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parse_evoxt_pricing_page_count_and_specs(pricing_html):
    products = parse_evoxt_pricing_page(pricing_html)
    assert len(products) == 33

    by_id = {p.external_id: p for p in products}

    # 1. 验证 Standard Network
    assert "1" in by_id
    p1 = by_id["1"]
    assert p1.name == "VM-0.5"
    assert p1.price == Decimal("2.99")
    assert p1.cpu_cores == 1
    assert p1.ram_gb == Decimal("0.5")
    assert p1.disk_gb == 5
    assert p1.bandwidth_gb == 500
    assert p1.port_mbps == 1000
    assert p1.location == "多机房 (可迁)"
    assert p1.line_tags == ["普通BGP"]
    assert p1.in_stock is True

    # 验证最高配置 VM-16
    assert "11" in by_id
    p11 = by_id["11"]
    assert p11.name == "VM-16"
    assert p11.price == Decimal("95.99")
    assert p11.cpu_cores == 16
    assert p11.ram_gb == Decimal("32")
    assert p11.disk_gb == 100
    assert p11.bandwidth_gb == 10000

    # 2. 验证 Premium Network (香港 / 大阪)
    assert "hk-prem-0.5" in by_id
    hk1 = by_id["hk-prem-0.5"]
    assert hk1.name == "香港/大阪（优质网络）-VM-0.5"
    assert hk1.price == Decimal("2.99")
    assert hk1.location == "香港 / 大阪"
    assert hk1.bandwidth_gb == 250

    assert "hk-prem-16" in by_id
    hk16 = by_id["hk-prem-16"]
    assert hk16.bandwidth_gb == 5000

    # 3. 验证 Premium Plus Network (马来西亚 CTG GIA + 9929 + CMI)
    assert "my-prem-0.5" in by_id
    my1 = by_id["my-prem-0.5"]
    assert my1.name == "马来西亚（优质网络）-VM-0.5"
    assert my1.price == Decimal("3.49")
    assert my1.location == "吉隆坡"
    assert my1.bandwidth_gb == 150
    assert set(my1.line_tags) == {"CN2 GIA", "9929", "CMI"}

    assert "my-prem-0.75" in by_id
    assert by_id["my-prem-0.75"].price == Decimal("4.99")
    assert by_id["my-prem-0.75"].bandwidth_gb == 250

    assert "my-prem-1" in by_id
    assert by_id["my-prem-1"].price == Decimal("5.99")
    assert by_id["my-prem-1"].bandwidth_gb == 300

    assert "my-prem-16" in by_id
    assert by_id["my-prem-16"].price == Decimal("95.99")
    assert by_id["my-prem-16"].bandwidth_gb == 4000


def test_evoxt_crawler_fetch_with_mock_client(pricing_html):
    crawler = EvoxtCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        if "pricing" in str(request.url):
            return httpx.Response(200, text=pricing_html)
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    products = crawler.fetch(client)
    assert len(products) == 33


def test_evoxt_crawler_fallback_to_dvps():
    crawler = EvoxtCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    fake_dvps_prods = [
        RawProduct(
            external_id=str(i),
            name=f"VM-{i}",
            price=Decimal("5.00"),
            currency="USD",
            billing_cycle="monthly",
            in_stock=False,
            location="多机房 (可迁)",
            cpu_cores=1,
            ram_gb=Decimal("1"),
            disk_gb=10,
        )
        for i in range(1, 10)
    ]

    with patch("app.crawler.dvps_source.DvpsSource.fetch_products", return_value=fake_dvps_prods):
        products = crawler.fetch(client)
        assert len(products) == 9
        assert products[0].in_stock is True
        assert products[0].port_mbps == 1000
        assert products[0].bandwidth_gb == 500


def test_evoxt_crawler_fallback_to_presets():
    crawler = EvoxtCrawler()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with patch("app.crawler.dvps_source.DvpsSource.fetch_products", return_value=[]):
        products = crawler.fetch(client)
        assert len(products) == len(PRESET_EVOXT_PRODUCTS)
        assert all(p.from_preset for p in products)
