"""GreenCloud（绿云）适配器。官网 https://greencloudvps.com ，订购系统 WHMCS twenty-one。

宁缺毋滥：全站 Budget/Ryzen/Storage 等廉价 KVM 有数百款、线路标注混杂，一律不收录。
只抓「CN Premium Optimized」分组——卡片 Location 字段明确写了回国线路：
- 东京：CN2GIA / CU PREMIUM / CMIN2
- 新加坡：CN2GIA / CU PREMIUM / CMI

库存只认 `.qty` 的 N Available。Order Now 在 0 库存时仍可点，不能当有货证据。
缺 pid / 价格 / CPU / 内存 的卡片直接丢弃，不猜规格。
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation

import httpx
from selectolax.parser import HTMLParser

from .base import MerchantCrawler, RawProduct, normalize_line_tags, normalize_location

logger = logging.getLogger(__name__)

BASE = "https://greencloudvps.com"
BILLING = f"{BASE}/billing"
STORE_URL = f"{BILLING}/store/cn-premium-optimized"

_RE_PID = re.compile(r"^product(\d+)$")
_RE_QTY = re.compile(r"(\d+)\s*Available", re.I)
_RE_PRICE = re.compile(r"\$\s*(\d+(?:\.\d+)?)\s*(USD)?", re.I)
_RE_NUM = re.compile(r"(\d+(?:\.\d+)?)")


def _feature_map(card) -> dict[str, str]:
    """WHMCS twenty-one: <li> <span class=feature-value>2GB</span> RAM </li>"""
    out: dict[str, str] = {}
    for li in card.css("li[id*='-feature']"):
        val_el = li.css_first(".feature-value")
        val = val_el.text(strip=True) if val_el else ""
        full = li.text(separator=" ", strip=True)
        label = full.replace(val, "", 1).strip().lower() if val else full.lower()
        if label:
            out[label] = val
    return out


def _gb(text: str) -> int | None:
    m = _RE_NUM.search(text or "")
    if not m:
        return None
    v = float(m.group(1))
    if re.search(r"tb", text, re.I):
        return int(v * 1000)
    return int(v)


def _ram_gb(text: str) -> Decimal | None:
    m = _RE_NUM.search(text or "")
    if not m:
        return None
    v = Decimal(m.group(1))
    if re.search(r"\bmb\b", text, re.I):
        return (v / 1024).quantize(Decimal("0.1"))
    return v


def _port_mbps(text: str) -> int | None:
    m = _RE_NUM.search(text or "")
    if not m:
        return None
    v = float(m.group(1))
    if re.search(r"gbps|g口", text, re.I):
        return int(v * 1000)
    return int(v)


def _cpu_cores(text: str) -> int | None:
    m = re.search(r"(\d+)\s*(?:cores?|v?cpu|核)", text or "", re.I)
    return int(m.group(1)) if m else None


def _line_tags(loc_text: str) -> list[str]:
    """CU PREMIUM 在绿云文案里对应联通精品（9929），不能写成 CMIN2。"""
    extra: list[str] = []
    if re.search(r"cu\s*premium|9929|cuii", loc_text, re.I):
        extra.append("9929")
    return normalize_line_tags(loc_text, extra)


def parse_greencloud_card(card) -> RawProduct | None:
    pid_m = _RE_PID.match(card.attributes.get("id", "") or "")
    if not pid_m:
        return None
    pid = pid_m.group(1)

    name_el = card.css_first(f"#product{pid}-name, header span")
    name = name_el.text(strip=True) if name_el else ""
    if not name:
        return None

    price_el = card.css_first(f"#product{pid}-price .price, .product-pricing .price")
    price_text = price_el.text(strip=True) if price_el else ""
    pm = _RE_PRICE.search(price_text) or _RE_PRICE.search(card.text(separator=" ", strip=True))
    if not pm:
        return None
    try:
        price = Decimal(pm.group(1))
    except InvalidOperation:
        return None
    if price <= 0:
        return None

    feats = _feature_map(card)
    ram = _ram_gb(feats.get("ram", ""))
    cpu = _cpu_cores(feats.get("cpu", ""))
    # 缺核心规格就不收录，避免把半解析套餐写进库
    if ram is None or cpu is None:
        return None

    disk = _gb(feats.get("hard drive", "") or feats.get("storage", ""))
    bw = _gb(feats.get("bandwidth", ""))
    port = _port_mbps(feats.get("port", ""))
    loc_raw = feats.get("location", "") or name
    location = normalize_location(loc_raw) or normalize_location(name)

    qty_el = card.css_first(".qty")
    qty_text = qty_el.text(strip=True) if qty_el else ""
    qty_m = _RE_QTY.search(qty_text)
    # 没有数量就当缺货：Order Now 在 0 Available 时仍存在，不能当有货
    in_stock = bool(qty_m and int(qty_m.group(1)) > 0)

    return RawProduct(
        external_id=pid,
        name=name[:250],
        price=price,
        currency="USD",
        billing_cycle="monthly",
        purchase_url=f"{BILLING}/cart.php?a=add&pid={pid}",
        in_stock=in_stock,
        location=location,
        line_tags=_line_tags(loc_raw),
        cpu_cores=cpu,
        ram_gb=ram,
        disk_gb=disk,
        bandwidth_gb=bw,
        port_mbps=port,
        stock_verified=True,
    )


def parse_greencloud_page(html: str) -> list[RawProduct]:
    tree = HTMLParser(html)
    products: list[RawProduct] = []
    seen: set[str] = set()
    for card in tree.css("div.product[id^='product']"):
        p = parse_greencloud_card(card)
        if p and p.external_id not in seen:
            seen.add(p.external_id)
            products.append(p)
    return products


# 规格来自 2026-09-08 官网 CN Premium 页；库存一律未核验，扫描时不得凭此改线上状态
PRESET_GREENCLOUD_PRODUCTS: list[RawProduct] = [
    RawProduct(external_id="2213", name="CN Premium Optimized Plan Mini (Tokyo)", price=Decimal("25.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2213", in_stock=False, location="东京", line_tags=["CN2 GIA", "9929", "CMIN2"], cpu_cores=1, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=500, port_mbps=500, from_preset=True, stock_verified=False),
    RawProduct(external_id="2077", name="CN Premium Optimized Plan 1 (Tokyo)", price=Decimal("45.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2077", in_stock=False, location="东京", line_tags=["CN2 GIA", "9929", "CMIN2"], cpu_cores=2, ram_gb=Decimal("4"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2079", name="CN Premium Optimized Plan 2 (Tokyo)", price=Decimal("85.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2079", in_stock=False, location="东京", line_tags=["CN2 GIA", "9929", "CMIN2"], cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=2000, port_mbps=1500, from_preset=True, stock_verified=False),
    RawProduct(external_id="2081", name="CN Premium Optimized Plan 3 (Tokyo)", price=Decimal("165.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2081", in_stock=False, location="东京", line_tags=["CN2 GIA", "9929", "CMIN2"], cpu_cores=8, ram_gb=Decimal("16"), disk_gb=160, bandwidth_gb=4000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2083", name="CN Premium Optimized Plan 4 (Tokyo)", price=Decimal("320.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2083", in_stock=False, location="东京", line_tags=["CN2 GIA", "9929", "CMIN2"], cpu_cores=8, ram_gb=Decimal("32"), disk_gb=320, bandwidth_gb=8000, port_mbps=3000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2305", name="CN Premium Optimized Plan Mini (Singapore)", price=Decimal("25.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2305", in_stock=False, location="新加坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=1, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=500, port_mbps=500, from_preset=True, stock_verified=False),
    RawProduct(external_id="2307", name="CN Premium Optimized Plan 1 (Singapore)", price=Decimal("45.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2307", in_stock=False, location="新加坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=2, ram_gb=Decimal("4"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2309", name="CN Premium Optimized Plan 2 (Singapore)", price=Decimal("85.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2309", in_stock=False, location="新加坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=2000, port_mbps=1500, from_preset=True, stock_verified=False),
    RawProduct(external_id="2311", name="CN Premium Optimized Plan 3 (Singapore)", price=Decimal("165.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2311", in_stock=False, location="新加坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=8, ram_gb=Decimal("16"), disk_gb=160, bandwidth_gb=4000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2313", name="CN Premium Optimized Plan 4 (Singapore)", price=Decimal("320.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BILLING}/cart.php?a=add&pid=2313", in_stock=False, location="新加坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=8, ram_gb=Decimal("32"), disk_gb=320, bandwidth_gb=8000, port_mbps=3000, from_preset=True, stock_verified=False),
]


class GreenCloudCrawler(MerchantCrawler):
    slug = "greencloud"
    name = "GreenCloud"
    default_interval_minutes = 5
    website = BASE
    crawl_method = "官方 WHMCS 商城 (CN Premium 优化系列)"
    aff_url_template = None

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        try:
            resp = client.get(STORE_URL)
            if resp.status_code == 200:
                products = parse_greencloud_page(resp.text)
                # 分组现有 10 款；解析过少说明页面改版，宁可不入库
                if len(products) >= 8:
                    return products
                logger.warning("[greencloud] parsed only %s CN Premium plans, falling back", len(products))
        except Exception as e:
            logger.warning("[greencloud] fetch error: %s", e)

        print(f"[greencloud] store unavailable, fallback to {len(PRESET_GREENCLOUD_PRODUCTS)} presets (stock unverified)")
        return [RawProduct(**p.__dict__) for p in PRESET_GREENCLOUD_PRODUCTS]
