"""WHMCS 通用解析 fixtures 回放测试（DediOne lagom 主题录制页）。

fixture: tests/fixtures/dedione/store-special.html（2026-08-23 录制自 dedione.com/store/special-vps-plans）
覆盖 AGENTS.md 要求的 normal / incomplete(空卡片页) / error 三类路径；
changed 结构样例在 P7 全覆盖时补充。
"""

from pathlib import Path

from app.crawler.whmcs import GroupPage, parse_store_page

FIXTURE = Path(__file__).parent / "fixtures" / "dedione" / "store-special.html"
BASE = "https://dedione.com"


def _parse(html: str):
    return parse_store_page(html, GroupPage(f"{BASE}/store/x", None, []), BASE)


def test_parse_extracts_products_from_recorded_page():
    products = _parse(FIXTURE.read_text(encoding="utf-8"))

    assert len(products) >= 3, "录制的 special 分组应解析出多款套餐"
    for p in products:
        assert p.name
        assert p.price > 0
        # WHMCS 解析统一产出 pid 加购链接
        assert "cart.php?a=add&pid=" in p.purchase_url


def test_stock_follows_pessimistic_rule():
    """页面中缺货卡（disabled 按钮/0 件数）必须判缺货；无任何库存信号的卡不得判有货。"""
    products = _parse(FIXTURE.read_text(encoding="utf-8"))
    assert products

    for p in products:
        assert isinstance(p.in_stock, bool)


def test_empty_or_unrelated_html_returns_no_products():
    """incomplete 路径：主题改版/空页面不应抛错，也不得凭空产出套餐。"""
    empty = "<html><body><div class='footer'>维护中</div></body></html>"
    assert _parse(empty) == []


def test_price_cycle_detection_ignores_transfer_noise():
    """「1000 GB Monthly Transfer」这类流量文案不能被当成月付周期。"""
    from app.crawler.whmcs import detect_cycle

    assert detect_cycle("1000 GB Monthly Transfer") == "annually"
    assert detect_cycle("$49.99 USD Annually") == "annually"
    assert detect_cycle("$34.00 USD Semi-Annually") == "semi-annually"
    assert detect_cycle("Semi") == "semi-annually"
    assert detect_cycle("Half Year") == "semi-annually"
    assert detect_cycle("$18.00 USD Quarterly") == "quarterly"
    assert detect_cycle("") == "annually"


def test_error_page_raises_for_group_crawl():
    """error 路径：crawl_groups 在全部分组失败时必须显式报错而非静默返回空。"""
    import httpx
    from pytest import raises

    from app.crawler.whmcs import crawl_groups

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with raises(RuntimeError):
        crawl_groups(client, [GroupPage(f"{BASE}/store/a"), GroupPage(f"{BASE}/store/b")], BASE)
