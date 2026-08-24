"""P7 全 provider fixture 回放测试（AGENTS.md Crawler Testing）。

- normal：录制的真实页面/接口响应（2026-08-24 录制；vmiss/vps 因源站盾拦截，
  fixture 为按解析器选择器构造的合成页面，文件头有标注）
- changed：结构变化（关键 class/key 改名）→ 解析出 0 款且不抛异常
- incomplete：空/缺失数据 → 0 款或按阈值回退预置目录（graceful degradation）
- error：HTTP 5xx → 各 adapter 契约不一（传播 or 降级），逐一固化为本测试

分层：parse+normalize 经 fetch(client) 端到端验证（MockTransport 注入，零外网）；
persistence（upsert 幂等/悲观库存）由 test_scan_products 覆盖，此处不重复。
"""

import json
from pathlib import Path

import httpx
import pytest

from app.crawler.bandwagon import BandwagonCrawler
from app.crawler.dedione import DediOneCrawler
from app.crawler.dmit import DmitCrawler
from app.crawler.sixsixyun import SixSixYunCrawler
from app.crawler.vmiss import VmissCrawler
from app.crawler.vps import VPSCrawler
from app.crawler.zgocloud import ZgoCloudCrawler
from app.crawler.whmcs import crawl_groups
from app.crawler.base import make_client

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(*parts: str) -> str:
    return (FIXTURES.joinpath(*parts)).read_text(encoding="utf-8")


def _mock_client(routes: list[tuple[str, int, str]]):
    """按 URL 子串顺序匹配返回 (status, body)；未命中返回 500。"""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for needle, status, body in routes:
            if needle in url:
                return httpx.Response(status, text=body)
        return httpx.Response(500, text="unrouted")

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


CF_CHALLENGE = "Just a moment... challenge-platform Please stand by"

# 合成 V.PS 分类页（HostBill categories_boxes 结构，选择器与 vps._parse_card 对齐）
_VPS_CARD_OK = """
<div class="cart-product" data-value="91">
  <h4>Cloud KVM Start</h4>
  <span class="product-price cycle-m">€ 10.00 EUR</span>
  <span class="product-price cycle-a">€ 100.00 EUR</span>
  <div><span class="text-muted">CPU</span><span class="font-weight-bold">2 vCore</span></div>
  <div><span class="text-muted">Memory</span><span class="font-weight-bold">4 GB</span></div>
  <div><span class="text-muted">Storage space</span><span class="font-weight-bold">80 GB NVMe</span></div>
  <div><span class="text-muted">Transfer</span><span class="font-weight-bold">2 TB</span></div>
</div>
"""
_VPS_CARD_OOS = _VPS_CARD_OK.replace('class="cart-product"', 'class="cart-product outofstock"', 1)
VPS_PAGE = f"<html><body>{_VPS_CARD_OK}{_VPS_CARD_OOS}</body></html>"
VPS_PAGE_CHANGED = VPS_PAGE.replace("cart-product", "offer-box").replace("product-price", "price-tag")

# 合成 66yun gid 页（WHMCS div.product 卡片，与 sixsixyun._parse_card 对齐）
_66YUN_CARD = """
<div class="product clearfix">
  <div class="product-desc"><strong>HK-CMI-150M</strong>
    <ul><li>CPU：1核</li><li>内存：1G</li><li>流量：800G</li><li>带宽：150M</li></ul>
  </div>
  <div class="product-pricing">
    <span>¥55.00 CNY /月</span>
    <a href="cart.php?a=add&pid=179">立即购买</a>
  </div>
</div>
"""


# ── bandwagon（JSON 源）─────────────────────────────────────────


class TestBandwagon:
    def test_normal_recorded_json(self):
        crawler = BandwagonCrawler()
        raws = crawler.fetch(_mock_client([("order/get-data", 200, _fixture("bandwagon", "get-data.json"))]))
        assert len(raws) >= 3
        first = raws[0]
        assert first.external_id and first.name
        assert float(first.price) > 0
        assert isinstance(first.in_stock, bool)
        # 多周期价格选项已解析（cents→元）
        assert any(o["billing_cycle"] in ("annually", "monthly") for o in first.price_options)

    def test_changed_schema_yields_zero(self):
        changed = json.dumps({"items": json.loads(_fixture("bandwagon", "get-data.json"))["products"]})
        raws = BandwagonCrawler().fetch(_mock_client([("order/get-data", 200, changed)]))
        assert raws == []

    def test_incomplete_empty_object(self):
        raws = BandwagonCrawler().fetch(_mock_client([("order/get-data", 200, "{}")]))
        assert raws == []

    def test_error_500_propagates(self):
        """契约：JSON 源 5xx 由 raise_for_status 向上抛，run_scan 层捕获并标记该商家失败。"""
        with pytest.raises(httpx.HTTPStatusError):
            BandwagonCrawler().fetch(_mock_client([("order/get-data", 500, "oops")]))


# ── dmit（双源合并 + 预置回退）──────────────────────────────────


class TestDmit:
    def test_normal_multi_source_merge_and_presets(self):
        routes = [
            ("monitor.vpszk.com", 200, _fixture("dmit", "plans.json")),
            ("vpsoso.com", 200, _fixture("dmit", "vpsoso.html")),
        ]
        raws = DmitCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 8                       # 触发预置补充分支
        assert any(p.from_preset for p in raws)     # 线上未覆盖的经典款以缺货态补齐
        live_ids = {p.external_id for p in raws if not p.from_preset}
        assert any(pid.startswith("dmit-") for pid in live_ids)

    def test_primary_down_fallback_source_used(self):
        routes = [
            ("monitor.vpszk.com", 200, "{not-json"),
            ("vpsoso.com", 200, _fixture("dmit", "vpsoso.html")),
        ]
        raws = DmitCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 1

    def test_all_sources_down_graceful_preset_fallback(self):
        """error 契约：双源全挂 → 预置目录兜底（悲观缺货），绝不抛异常阻塞其他商家。"""
        raws = DmitCrawler().fetch(_mock_client([("er-api", 500, "")]))  # 无路由命中→全 500
        assert len(raws) == 20                      # DMIT_PRESETS 数量
        assert all(p.from_preset and not p.in_stock for p in raws)


# ── zgocloud（HTML 分组页，错误向上传播）────────────────────────


class TestZgocloud:
    def test_normal_recorded_group_page(self):
        routes = [("clients.zgovps.com", 200, _fixture("zgocloud", "special-offer.html"))]
        raws = ZgoCloudCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 1
        p = raws[0]
        assert p.external_id and p.name
        assert float(p.price) > 0
        assert p.price_options, "多周期价格选项应被解析"

    def test_changed_layout_yields_zero_without_error(self):
        changed = _fixture("zgocloud", "special-offer.html").replace("<form", "<div").replace("</form>", "</div>")
        raws = ZgoCloudCrawler().fetch(_mock_client([("clients.zgovps.com", 200, changed)]))
        assert raws == []

    def test_incomplete_empty_html(self):
        raws = ZgoCloudCrawler().fetch(_mock_client([("clients.zgovps.com", 200, "<html><body></body></html>")]))
        assert raws == []

    def test_error_500_propagates(self):
        """契约：分组页 5xx 由 raise_for_status 上抛（run_scan 层捕获标记失败）。"""
        with pytest.raises(httpx.HTTPStatusError):
            ZgoCloudCrawler().fetch(_mock_client([("clients.zgovps.com", 500, "oops")]))


# ── dedione（WHMCS lagom，经 DediOneCrawler.fetch 集成回放）─────


class TestDediOne:
    def test_normal_recorded_fixture_through_crawler(self):
        body = _fixture("dedione", "store-special.html")
        crawler = DediOneCrawler()
        routes = [(page.url, 200, body) for page in crawler.PAGES]
        raws = crawler.fetch(_mock_client(routes))
        assert len(raws) >= 3
        assert all("cart.php?a=add&pid=" in p.purchase_url for p in raws)

    def test_error_all_groups_fail_raises(self):
        """error 契约：全部分组失败必须显式抛错而非静默空列表。"""
        crawler = DediOneCrawler()
        routes = [(page.url, 500, "oops") for page in crawler.PAGES]
        with pytest.raises(RuntimeError):
            crawler.fetch(_mock_client(routes))


# ── sixsixyun（WHMCS div.product + 阈值回退预置）────────────────


class TestSixSixYun:
    def test_normal_recorded_gid_page(self):
        body = _fixture("sixsixyun", "cart-gid6.html")
        # 同页喂给全部 gid：live ≥ 阈值(5) 时走实时目录分支
        routes = [("666clouds.com/cart.php?gid=", 200, body)]
        raws = SixSixYunCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 5
        distinct = {p.external_id for p in raws}
        assert len(distinct) >= 2                   # 录制页含 ≥2 款不同套餐
        assert all("cart.php?a=add&pid=" in p.purchase_url for p in raws)

    def test_incomplete_pages_threshold_falls_back_to_presets(self):
        """incomplete 契约：实时解析不足阈值 → 预置目录兜底（悲观缺货）。"""
        raws = SixSixYunCrawler().fetch(_mock_client([("666clouds.com", 200, "<html></html>")]))
        assert len(raws) >= 27                      # PRESET_66YUN_PRODUCTS 全量
        assert all(not p.in_stock for p in raws)    # 预置一律悲观缺货

    def test_changed_markup_falls_back_to_presets(self):
        changed = _fixture("sixsixyun", "cart-gid6.html").replace('class="product', 'class="offer')
        raws = SixSixYunCrawler().fetch(_mock_client([("666clouds.com", 200, changed)]))
        assert len(raws) >= 27 and all(not p.in_stock for p in raws)

    def test_error_500_per_gid_isolated_then_presets(self):
        """error 契约：单 gid 失败被隔离不中断其他 gid；整体不足则回退预置。"""
        raws = SixSixYunCrawler().fetch(_mock_client([("666clouds.com", 500, "oops")]))
        assert len(raws) >= 27


# ── vmiss（Cloudflare 盾 + stockvps 兜底 + 静态预置）────────────


def _stockvps_client() -> httpx.Client:
    """stockvps.org 走录制 fixture；其余 URL 一律返回 Cloudflare 挑战页。"""
    body = _fixture("vmiss", "stockvps-page.html")

    def handler(request: httpx.Request) -> httpx.Response:
        if "stockvps.org" in str(request.url):
            return httpx.Response(200, text=body)
        return httpx.Response(200, text=CF_CHALLENGE)

    return httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0)


class TestVmiss:
    def test_normal_synthetic_lagom_pages(self):
        """合成 fixture：app.vmiss.com 直连被 CF 拦截（录制 403），
        按 WHMCS lagom 结构构造（同 dedione 已验证的解析路径）。"""
        body = _fixture("dedione", "store-special.html")
        routes = [("app.vmiss.com/store/", 200, body), ("stockvps.org", 500, "")]
        raws = VmissCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 10                      # 过实时目录阈值
        assert all(not p.from_preset for p in raws)

    def test_blocked_by_cloudflare_falls_back_to_stock_overlay(self):
        """blocked 契约：挑战页全部跳过 → 第三方监控源覆写预置库存。
        fixture 为 stockvps.org 真实录制格式（转义 JSON 内嵌页面、/go/vmiss/{pid} 相对链接）。"""
        raws = VmissCrawler().fetch(_stockvps_client())
        assert len(raws) >= 30                      # PRESET_VMISS_PRODUCTS
        assert all(p.from_preset for p in raws)
        by_id = {p.external_id: p for p in raws}
        assert by_id["62"].in_stock is True         # 监控源 stock=-1 → 有货覆写
        assert by_id["70"].in_stock is False        # 监控源 stock=0 → 缺货映射
        assert by_id["7"].in_stock is False         # 监控源未覆盖的 pid 保持悲观缺货

    def test_error_everything_down_static_presets_oos(self):
        """error 契约：官网被拦 + 监控源不可用 → 静态预置（全缺货），不抛异常。"""
        raws = VmissCrawler().fetch(_mock_client([]))
        assert len(raws) >= 30
        assert all(p.from_preset and not p.in_stock for p in raws)


# ── vps（HostBill 卡片，合成 fixture；回退带加购页库存校验）──────


class TestVps:
    def test_normal_synthetic_category_page(self):
        """合成 fixture：vps.hosting 直连被拦（录制 403），按 HostBill 模板构造。"""
        routes = [("vps.hosting/cart/", 200, VPS_PAGE)]
        raws = VPSCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 10                      # 同页喂 12 个分类，过实时阈值
        tokyo = [p for p in raws if p.name.startswith("NRT")]
        assert tokyo, "东京分类应产出 NRT 前缀套餐"
        one = tokyo[0]
        assert one.currency == "EUR"
        assert {o["billing_cycle"] for o in one.price_options} >= {"monthly", "annually"}
        stocks = [p.in_stock for p in raws]
        assert True in stocks and False in stocks   # outofstock 标记生效

    def test_changed_markup_falls_back_to_pid_stock_check(self):
        routes = [
            ("vps.hosting/cart/tokyo", 200, VPS_PAGE_CHANGED),
            ("vps.hosting/?cmd=cart", 200, "<html><body>无库存标记</body></html>"),
        ]
        raws = VPSCrawler().fetch(_mock_client(routes))
        assert len(raws) >= 10                      # 预置目录兜底
        assert all(p.from_preset for p in raws)

    def test_error_categories_down_falls_back_to_presets(self):
        raws = VPSCrawler().fetch(_mock_client([("vps.hosting", 500, "oops")]))
        assert len(raws) >= 10
        assert all(p.from_preset for p in raws)
