"""Line-tag preservation, WHMCS cycle parse, leak predicate via shipped modules."""

from pathlib import Path

import pytest

from app.crawler.base import normalize_line_tags
from app.crawler.whmcs import GroupPage, detect_cycle, parse_store_page


def test_cmi_and_softbank_not_mapped_to_bgp():
    cmi = normalize_line_tags("香港 CMI 大带宽", ["CMI"])
    assert "CMI" in cmi
    assert "普通BGP" not in cmi

    sb = normalize_line_tags("日本软银 BBTEC", ["软银"])
    assert "软银" in sb
    assert "普通BGP" not in sb


def test_detect_cycle_ignores_monthly_transfer():
    assert detect_cycle("1000 GB Monthly Transfer") == "annually"
    assert detect_cycle("Annually") == "annually"
    assert detect_cycle("Monthly") == "monthly"


def test_whmcs_uses_price_cycle_not_transfer_phrase():
    html = """
    <div class="package" id="product42">
      <h3 class="package-title">LAX Promo</h3>
      <div class="price-amount">$49.99 USD</div>
      <div class="price-cycle">Annually</div>
      <div>1000 GB Monthly Transfer</div>
      <a class="btn-order-now" href="/cart.php?a=add&pid=42">Order Now</a>
      <div class="package-qty">3 Available</div>
    </div>
    """
    products = parse_store_page(html, GroupPage("https://shop.example/store/lax"), "https://shop.example")
    assert len(products) == 1
    assert products[0].billing_cycle == "annually"
    assert products[0].in_stock is True



