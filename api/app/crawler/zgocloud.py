"""ZgoCloud（原 ZgoVPS）适配器。商店在 https://clients.zgovps.com （WHMCS 定制模板）。

其商店页非标准 WHMCS 卡片，结构为（已对照真实页面校准）：
  <form action="" method="post">
    <input name="id" type="hidden" value="160">   ← 产品 pid
    <strong>套餐名</strong>
    <ul><li>配置...</li></ul>
    <select name="cycle"><option>$45.00 USD Annually</option></select>
    <button class="btn-success | disabled">Continue</button>   ← disabled = 缺货
  </form>
"""

import re
from decimal import Decimal, InvalidOperation

import httpx
from selectolax.parser import HTMLParser

from .base import MerchantCrawler, RawProduct, extract_line_tags, extract_location, parse_specs
from .whmcs import GroupPage, detect_cycle

BASE = "https://clients.zgovps.com"

_RE_PRICE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)\s*USD\s*(\w+)", re.I)


class ZgoCloudCrawler(MerchantCrawler):
    slug = "zgocloud"
    name = "ZgoCloud"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://clients.zgovps.com"
    aff_url_template = None

    PAGES = [
        GroupPage(f"{BASE}/index.php?/cart/special-offer/", None, []),
        GroupPage(f"{BASE}/index.php?/cart/los-angeles-amd-optimised-vps/", "洛杉矶", ["CN2 GIA", "9929", "CMIN2"]),
        # 官网标注 "9929&CMIN2, China Optimised"
        GroupPage(f"{BASE}/index.php?/cart/los-angeles-intel-performance-vps/", "洛杉矶", ["9929", "CMIN2"]),
        # 官网标注 "International network, not optimized for China"
        GroupPage(f"{BASE}/index.php?/cart/los-angeles-global-vps/", "洛杉矶", ["国际线路"]),
        # 官网标注 "IIJ, not optimized for China"（IIJ 为日本国际线路）
        GroupPage(f"{BASE}/index.php?/cart/osaka-amd-performance-vps/", "日本大阪", ["国际线路"]),
        # 官网标注 "BGP Network"
        GroupPage(f"{BASE}/index.php?/cart/hongkong-amd-vps/", "中国香港", ["BGP"]),
        GroupPage(f"{BASE}/index.php?/cart/tokyo-intel-vps/", "日本东京", ["BGP"]),
        GroupPage(f"{BASE}/index.php?/cart/falkenstein-intel-vps/", "德国法尔肯施泰因", ["国际线路"]),
    ]

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        results: list[RawProduct] = []
        for group in self.PAGES:
            resp = client.get(group.url)
            resp.raise_for_status()
            results.extend(self._parse(resp.text, group))
        return results

    def _parse(self, html: str, group: GroupPage) -> list[RawProduct]:
        tree = HTMLParser(html)
        products: list[RawProduct] = []

        for form in tree.css("form"):
            id_input = form.css_first('input[name="id"][type="hidden"]')
            name_node = form.css_first("strong")
            cycle_options = form.css('select[name="cycle"] option')
            if not (id_input and name_node and cycle_options):
                continue

            pid = id_input.attributes.get("value", "")
            name = name_node.text(strip=True)
            if not pid or not name:
                continue

            price_options: list[dict] = []
            price = None
            billing_cycle = "annually"
            for price_option in cycle_options:
                m = _RE_PRICE.search(price_option.text(strip=True))
                if not m:
                    continue
                try:
                    opt_price = Decimal(m.group(1))
                except InvalidOperation:
                    continue
                if opt_price <= 0:
                    continue
                opt_cycle = detect_cycle(m.group(2) or price_option.text(strip=True))
                price_options.append(
                    {
                        "billing_cycle": opt_cycle,
                        "price": float(opt_price),
                        "currency": "USD",
                        "purchase_url": f"{BASE}/index.php?/cart/",
                    }
                )
                if price is None:
                    price = opt_price
                    billing_cycle = opt_cycle
            if price is None:
                continue

            # 库存判定（正向确认原则）：按钮存在且未禁用才算有货；
            # 按钮选择器失配（btn 为 None）时判缺货而非默认有货，防止主题改版静默误报
            btn = form.css_first('button[type="submit"]')
            btn_class = (btn.attributes.get("class", "") if btn else "") or ""
            btn_disabled_attr = btn.attributes.get("disabled") if btn else None
            form_text = form.text(separator=" ", strip=True).lower()
            has_oos_signal = (
                "disabled" in btn_class
                or btn_disabled_attr is not None
                or any(kw in form_text for kw in ("out of stock", "sold out", "缺货", "售罄", "暂无库存"))
            )
            in_stock = btn is not None and not has_oos_signal

            specs_text = form.text(separator=" ", strip=True)
            # 注意：zgocloud 是定制 WHMCS，加购必须 POST 表单（action=add&id=pid），
            # GET 的 cart.php?a=add&pid= 会 404。go 路由会针对该商家构造自动提交表单。
            p = RawProduct(
                external_id=pid,
                name=name[:250],
                price=price,
                currency="USD",
                billing_cycle=billing_cycle,
                price_options=price_options,
                purchase_url=f"{BASE}/index.php?/cart/",
                in_stock=in_stock,
                location=group.location or extract_location(name),
                line_tags=list(group.line_tags),
            )
            parse_specs(specs_text, p)
            # 线路：优先用分组硬编码标签（分组级别固定线路属性，如 Optimised 三网、Global 国际线路）；
            # 仅当分组未标注线路时才从规格文本提取（如 special-offer 混合分组，文本内含线路关键词）。
            if not p.line_tags:
                for tag in extract_line_tags(specs_text):
                    if tag not in p.line_tags:
                        p.line_tags.append(tag)
            if price == Decimal("52.00") and ("Los Angeles" in name or "Optimised" in name):
                p.recommended = True
            products.append(p)

        return products
