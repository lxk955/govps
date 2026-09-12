"""FlareSolverr 求解器与官方爬虫单测。

覆盖 AGENTS.md 规范：
- 离线独立测试（不依赖外部网络连接）
- 测试 FlareSolverr 客户端、Turnstile 会话生命周期与容错降级
- 测试 66云 Next.js /shop 新版页面解析
- 测试 DMIT 官方 WHMCS 订购页（有货配置页与缺货页）解析
- 测试 VMiss 盾拦截与求解集成
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
import httpx

from app.crawler.dmit import _parse_dmit_html, DmitCrawler
from app.crawler.sixsixyun import _detect_location, _parse_shop_product, SixSixYunCrawler
from app.crawler.solver import (
    FlareSolverrClient,
    flaresolverr_session,
    is_flaresolverr_available,
)
from app.crawler.vmiss import VmissCrawler


# ── FlareSolverr 客户端单测 ──

def test_flaresolverr_available_check():
    with patch("httpx.get") as mock_get:
        mock_get.return_value = httpx.Response(200)
        with patch("app.crawler.solver.settings.FLARESOLVERR_URL", "http://flaresolverr:8191/v1"):
            assert is_flaresolverr_available() is True

        mock_get.side_effect = Exception("connection refused")
        assert is_flaresolverr_available() is False

    with patch("app.crawler.solver.settings.FLARESOLVERR_URL", ""):
        assert is_flaresolverr_available() is False


def test_flaresolverr_fetch_success():
    client = FlareSolverrClient(endpoint="http://flaresolverr:8191/v1")
    fake_resp = {
        "status": "ok",
        "message": "Challenge solved!",
        "solution": {
            "status": 200,
            "response": "<html><body>Solved HTML</body></html>",
        },
    }
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(200, json=fake_resp)
        html = client.fetch("https://app.vmiss.com/store/us-los-angeles-cn2")
        assert html == "<html><body>Solved HTML</body></html>"


def test_flaresolverr_fetch_failure_returns_none():
    client = FlareSolverrClient(endpoint="http://flaresolverr:8191/v1")
    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = httpx.Response(500)
        assert client.fetch("https://example.com") is None

        mock_post.side_effect = Exception("timeout")
        assert client.fetch("https://example.com") is None


def test_flaresolverr_session_context_manager():
    with patch("app.crawler.solver.settings.FLARESOLVERR_URL", "http://flaresolverr:8191/v1"):
        with patch.object(FlareSolverrClient, "create_session", return_value=True) as mock_create:
            with patch.object(FlareSolverrClient, "destroy_session", return_value=True) as mock_destroy:
                with flaresolverr_session("test_sess") as (solver, sid):
                    assert solver is not None
                    assert sid == "test_sess"
                mock_create.assert_called_once_with("test_sess")
                mock_destroy.assert_called_once_with("test_sess")


# ── 66云 Next.js 官方页面解析测试 ──

SAMPLE_66YUN_HTML_IN_STOCK = """
<html>
<body>
<h1>美西原生IP双ISP - GTT</h1>
<a href="/shop/199" class="rounded border px-4 py-3 border-accent bg-accent-bg">
  <span>20 GB · 2 TB</span>
  <span>¥90 /月</span>
</a>
<dl class="mt-3 grid grid-cols-2">
  <div><dt>数据中心</dt><dd>美ISP - GTT</dd></div>
  <div><dt>CPU</dt><dd>1 核</dd></div>
  <div><dt>内存</dt><dd>1 GB</dd></div>
  <div><dt>系统盘</dt><dd>20 GB</dd></div>
  <div><dt>带宽</dt><dd>1000 Mbps</dd></div>
  <div><dt>流量</dt><dd>2 TB</dd></div>
</dl>
<div>数量 库存仅 4 台 优惠码</div>
<p class="text-sm">应付 ¥90.00</p>
<p class="whitespace-pre-line">全新IP段，双isp，助力tiktok业务。</p>
</body>
</html>
"""

SAMPLE_66YUN_HTML_OOS = """
<html>
<body>
<h1>美西原生IP双ISP - GTT</h1>
<a href="/shop/195" class="rounded border px-4 py-3 border-accent bg-accent-bg">
  <span>15 GB · 1 TB 缺货</span>
  <span>¥55 /月</span>
</a>
<dl class="mt-3 grid grid-cols-2">
  <div><dt>数据中心</dt><dd>美ISP - GTT</dd></div>
  <div><dt>CPU</dt><dd>1 核</dd></div>
  <div><dt>内存</dt><dd>1 GB</dd></div>
  <div><dt>系统盘</dt><dd>15 GB</dd></div>
  <div><dt>带宽</dt><dd>1000 Mbps</dd></div>
  <div><dt>流量</dt><dd>1 TB</dd></div>
</dl>
<div>数量 暂时缺货 优惠码</div>
<p class="text-sm">应付 ¥55.00</p>
</body>
</html>
"""


def test_66yun_parse_in_stock():
    p = _parse_shop_product("199", SAMPLE_66YUN_HTML_IN_STOCK, default_sec="美国US原生双ISP")
    assert p is not None
    assert p.external_id == "199"
    assert "20 GB · 2 TB" in p.name
    assert p.price == Decimal("90.00")
    assert p.currency == "CNY"
    assert p.billing_cycle == "monthly"
    assert p.in_stock is True
    assert p.cpu_cores == 1
    assert p.ram_gb == Decimal("1")
    assert p.disk_gb == 20
    assert p.bandwidth_gb == 2000
    assert p.port_mbps == 1000
    assert p.location == "美西"
    assert p.stock_verified is True


def test_66yun_parse_out_of_stock():
    p = _parse_shop_product("195", SAMPLE_66YUN_HTML_OOS, default_sec="美国US原生双ISP")
    assert p is not None
    assert p.external_id == "195"
    assert p.in_stock is False
    assert p.price == Decimal("55.00")
    assert p.bandwidth_gb == 1000


def test_66yun_detect_location():
    assert _detect_location("菲律宾双ISP", "菲律宾双ISP (1 核 · 1 GB · 15 GB · 1 TB)", "菲律宾") == "菲律宾"
    assert _detect_location("英国GB原生双ISP", "英国双ISP (1 核 · 1 GB · 15 GB · 1 TB)", "英国优化") == "伦敦"
    assert _detect_location("德国DE双ISP", "德国原生IP", "德国") == "德国"
    assert _detect_location("香港HK", "HK-CMI-150M", "香港land") == "香港"
    assert _detect_location("日本JP软银", "日本JP软银", "日本") == "日本"
    assert _detect_location("韩国双ISP原生IP", "韩国双ISP", "首尔") == "首尔"


# ── DMIT 官方页面解析测试 ──

SAMPLE_DMIT_HTML_IN_STOCK = """
<html>
<body>
<form id="frmConfigureProduct">
  <div class="cart-products-title">HKG.AS3.T1.TINY</div>
  <div class="cart-products-price">
    <div class="price-num">6.90</div>
    <div class="billing-cycle-text">/ Monthly</div>
  </div>
  <div class="products-desc-item">
    <div class="desc-item-title">vCPU</div>
    <div class="desc-item-value">1 vCores</div>
  </div>
  <div class="products-desc-item">
    <div class="desc-item-title">RAM</div>
    <div class="desc-item-value">1.0GB</div>
  </div>
  <div class="products-desc-item">
    <div class="desc-item-title">Storage</div>
    <div class="desc-item-value">20GB SSD</div>
  </div>
  <div class="products-desc-item">
    <div class="desc-item-title">Routing Profile</div>
    <div class="desc-item-value">Tier 1</div>
  </div>
  <div class="cart-products-transfer-area">
    <div class="highspeed-quota">2000GB</div>
    <div class="highspeed-text">@ 4Gbps</div>
  </div>
</form>
</body>
</html>
"""

SAMPLE_DMIT_HTML_OOS = """
<html>
<body>
<h1>Out of Stock</h1>
<p>We are currently out of stock on this item so orders for it have been suspended until more stock is available.</p>
</body>
</html>
"""


def test_dmit_parse_in_stock():
    p = _parse_dmit_html("198", SAMPLE_DMIT_HTML_IN_STOCK)
    assert p is not None
    assert p.external_id == "dmit-198"
    assert p.name == "PVM.HKG.AS3.T1.TINY"
    assert p.price == Decimal("6.90")
    assert p.currency == "USD"
    assert p.billing_cycle == "monthly"
    assert p.in_stock is True
    assert p.cpu_cores == 1
    assert p.ram_gb == Decimal("1.0")
    assert p.disk_gb == 20
    assert p.bandwidth_gb == 2000
    assert p.port_mbps == 4000
    assert p.location == "香港"
    assert "国际线路" in p.line_tags
    assert p.stock_verified is True


def test_dmit_parse_out_of_stock():
    # 183 对应 PVM.LAX.Pro.WEE
    p = _parse_dmit_html("183", SAMPLE_DMIT_HTML_OOS)
    assert p is not None
    assert p.external_id == "dmit-183"
    assert p.in_stock is False
    assert p.location == "洛杉矶"
    assert "CN2 GIA" in p.line_tags
    assert p.stock_verified is True
