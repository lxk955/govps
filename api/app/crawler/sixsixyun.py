"""66云（六六云）适配器。官网 https://666clouds.com（WHMCS 系统）。

覆盖机房与优化线路：
- 香港：CMI / 普通BGP 大带宽（gid=6）
- 首尔：韩国原生 IP / 双 ISP 原生（gid=16）
- 日本：日本软银 BBTEC / 联通优化大带宽（gid=19）
- 美西：美西双 ISP / 9929 / CU4837 / G口 / CN2 GIA / GTT / NTT（gid=21）
- 伦敦：英国双 ISP / 英国三网双向优化 9929（gid=22）
- 德国：德国原生 IP / 国际大带宽（gid=25）

策略：
1. 实时：抓取 cart.php?gid={gid} 分组页面，解析 div.product 卡片及库存与规格；
2. 回退：静态预置目录兜底（与 DMIT/VMiss 一致采用悲观默认，全部标记缺货，
   由实时抓取覆写真实库存；避免源站抖动时把整目录误判为有货、触发虚假补货通知）。
"""

import re
from decimal import Decimal

import httpx
from selectolax.parser import HTMLParser

from .base import MerchantCrawler, RawProduct

BASE = "https://666clouds.com"

# 66云核心业务分组定义
CATEGORIES: list[tuple[int, str, list[str]]] = [
    (6, "香港", ["CMI"]),
    (16, "首尔", ["国际线路"]),
    (19, "日本", ["软银"]),
    (21, "美西", ["9929", "4837", "CN2 GIA"]),
    (22, "伦敦", ["9929", "三网优化"]),
    (25, "德国", ["国际线路"]),
]


def _detect_line_tags(name: str, desc: str, default_tags: list[str]) -> list[str]:
    combined = f"{name} {desc}".lower()
    if "9929" in combined:
        return ["9929"]
    if "4837" in combined:
        return ["4837"]
    if "cn2" in combined or "gia" in combined:
        return ["CN2 GIA"]
    if "cmi" in combined:
        return ["CMI"]
    if "软银" in combined or "bbtec" in combined or "softbank" in combined:
        return ["软银"]
    return list(default_tags)


def _parse_card(card, location: str, default_tags: list[str]) -> RawProduct | None:
    name_node = card.css_first('[id$="-name"], header span, .package-title, .product-name')
    name = name_node.text(strip=True) if name_node else ""
    if not name:
        return None

    price_node = card.css_first(".price, .product-pricing")
    price_text = price_node.text(strip=True) if price_node else ""
    m_price = re.search(r"(\d+(?:\.\d{1,2})?)", price_text)
    if not m_price:
        return None
    price = Decimal(m_price.group(1))

    order_btn = card.css_first('a[href*="pid="]')
    if not order_btn:
        return None
    href = order_btn.attributes.get("href", "")
    m_pid = re.search(r"pid=(\d+)", href)
    if not m_pid:
        return None
    pid = m_pid.group(1)

    btn_class = order_btn.attributes.get("class", "") or ""
    qty_node = card.css_first(".qty")
    qty_text = qty_node.text(strip=True) if qty_node else ""
    qty_m = re.search(r"(\d+)\s*(?:可用|Available)", qty_text)

    card_text = card.text(separator=" ", strip=True).lower()
    has_oos = (
        "disabled" in btn_class
        or (qty_m and int(qty_m.group(1)) == 0)
        or "缺货" in card_text
        or "out of stock" in card_text
        or "售罄" in card_text
    )
    # 正向确认：有剩余件数，或文案明确「有货」；仅「立即购买」按钮不足以证明有货
    has_stock_signal = (qty_m is not None and int(qty_m.group(1)) > 0) or (
        "有货" in card_text or "in stock" in card_text
    )

    desc_node = card.css_first(".product-desc, [id$='-description']")
    desc = desc_node.text(separator="\n", strip=True) if desc_node else ""
    clean = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "", desc)

    tags = _detect_line_tags(name, desc, default_tags)

    p = RawProduct(
        external_id=pid,
        name=name,
        price=price,
        currency="CNY",
        billing_cycle="monthly",
        purchase_url=f"{BASE}/cart.php?a=add&pid={pid}",
        in_stock=bool(has_stock_signal) and not has_oos,
        location=location,
        line_tags=tags,
    )

    # 标题特征 (如 2H2G, 4H4G)
    m_hg = re.search(r"(\d+)\s*[hH核]\s*(\d+)\s*[gG]", name)
    if m_hg:
        p.cpu_cores = int(m_hg.group(1))
        p.ram_gb = Decimal(m_hg.group(2))

    for raw_line in clean.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if p.cpu_cores is None:
            m = re.search(r"(\d+)\s*v?cpu", line, re.I) or re.search(r"vcpu[：:\s]*(\d+)", line, re.I)
            if m:
                p.cpu_cores = int(m.group(1))
        if p.ram_gb is None:
            m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GB|G)\s*内存", line, re.I) or re.search(
                r"内存[：:\s]*(\d+(?:\.\d+)?)\s*(GB|G|MB|M)(?![a-zA-Z])", line, re.I
            )
            if m:
                val = Decimal(m.group(1))
                unit = (m.group(2) if m.lastindex >= 2 and m.group(2) else "G").upper()
                p.ram_gb = val / 1024 if unit.startswith("M") else val
        if p.disk_gb is None:
            m = re.search(r"硬盘[：:\s]*(\d+(?:\.\d+)?)\s*(TB|T|GB|G)?", line, re.I) or re.search(
                r"(\d+)\s*(?:GB|G)\s*SSD", line, re.I
            )
            if m:
                val = int(Decimal(m.group(1)))
                unit = (m.group(2) or "G").upper() if m.lastindex >= 2 and m.group(2) else "G"
                p.disk_gb = val * 1024 if unit.startswith("T") else val
        if p.bandwidth_gb is None:
            m = re.search(r"流量[：:\s]*(\d+(?:\.\d+)?)\s*(TB|T|GB|G)?", line, re.I) or re.search(
                r"(\d+(?:\.\d+)?)\s*(TB|T|GB|G)\s*流量", line, re.I
            )
            if m:
                val = int(Decimal(m.group(1)))
                unit = (m.group(2) or "G").upper() if m.lastindex >= 2 and m.group(2) else "G"
                p.bandwidth_gb = val * 1024 if unit.startswith("T") else val
        if p.port_mbps is None:
            m = re.search(r"带宽[：:\s]*(\d+(?:\.\d+)?)\s*(Mbits|Mbps|M|Gbits|Gbps|G|G口)?", line, re.I) or re.search(
                r"(\d+)\s*(?:Mbps|Mbits|M)\s*峰值带宽", line, re.I
            )
            if m:
                val = int(Decimal(m.group(1)))
                unit = (m.group(2) or "M").upper() if m.lastindex >= 2 and m.group(2) else "M"
                p.port_mbps = val * 1000 if "G" in unit else val

    return p


def _fetch_live(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    for gid, location, default_tags in CATEGORIES:
        url = f"{BASE}/cart.php?gid={gid}"
        try:
            resp = client.get(url, timeout=12.0)
            if resp.status_code != 200:
                continue
            tree = HTMLParser(resp.text)
            cards = tree.css("div.product")
            for card in cards:
                p = _parse_card(card, location, default_tags)
                if p:
                    products.append(p)
        except Exception as e:
            print(f"[66yun] gid {gid} fetch failed: {e}")
    return products


# 预置基准套餐目录（27 款主流套餐）
PRESET_66YUN_PRODUCTS: list[RawProduct] = [
    RawProduct(external_id="179", name="HK-CMI-150M", price=Decimal("55.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=179", in_stock=False, location="香港", line_tags=['CMI'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=800, port_mbps=150),
    RawProduct(external_id="131", name="HK-CMI-normal", price=Decimal("50.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=131", in_stock=False, location="香港", line_tags=['CMI'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=50),
    RawProduct(external_id="23", name="HK-CMI-medium-2H2G-50M", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=23", in_stock=False, location="香港", line_tags=['CMI'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=None, bandwidth_gb=1200, port_mbps=50),
    RawProduct(external_id="209", name="韩国双ISP IP", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=209", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="210", name="韩国双ISP - 升级2H2G2T", price=Decimal("150.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=210", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=2000, port_mbps=200),
    RawProduct(external_id="87", name="韩国原生IP", price=Decimal("60.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=87", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=15, bandwidth_gb=800, port_mbps=30),
    RawProduct(external_id="94", name="日本JP软银", price=Decimal("55.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=94", in_stock=False, location="日本", line_tags=['软银'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=500),
    RawProduct(external_id="206", name="日本JP软银 4H4G", price=Decimal("200.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=206", in_stock=False, location="日本", line_tags=['软银'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=None, bandwidth_gb=2000, port_mbps=500),
    RawProduct(external_id="155", name="日本软银 - 联通首选", price=Decimal("48.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=155", in_stock=False, location="日本", line_tags=['软银'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=500),
    RawProduct(external_id="169", name="日本软银大流量 - 联通起飞", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=169", in_stock=False, location="日本", line_tags=['软银'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=2000, port_mbps=500),
    RawProduct(external_id="191", name="美西原生IP双ISP - NTT（新IP）", price=Decimal("50.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=191", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="192", name="美西原生IP双ISP - NTT（新IP）- 2TB流量", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=192", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="195", name="美西原生IP双ISP - GTT", price=Decimal("55.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=195", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="199", name="美西原生IP双ISP - GTT - 2TB流量", price=Decimal("90.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=199", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="193", name="美国原生IP三网CN2 GIA大带宽", price=Decimal("55.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=193", in_stock=False, location="美西", line_tags=['CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=800, port_mbps=200),
    RawProduct(external_id="187", name="美西原生IP双ISP - 9929优化线路（新手首选）", price=Decimal("55.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=187", in_stock=False, location="美西", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="157", name="美西原生IP双ISP /CU4837/G口", price=Decimal("50.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=157", in_stock=False, location="美西", line_tags=['4837'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="188", name="美西原生IP双ISP /CU4837/G口 - 2TB流量", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=188", in_stock=False, location="美西", line_tags=['4837'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="170", name="美西原生IP双ISP - 国际带宽", price=Decimal("50.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=170", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="171", name="美西原生IP双ISP-国际带宽 - 4TB流量", price=Decimal("80.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=171", in_stock=False, location="美西", line_tags=['9929', '4837', 'CN2 GIA'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="148", name="英国双ISP（新）", price=Decimal("60.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=148", in_stock=False, location="伦敦", line_tags=['9929', '三网优化'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="201", name="英国双ISP - 高配版", price=Decimal("120.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=201", in_stock=False, location="伦敦", line_tags=['9929', '三网优化'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=None, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="211", name="英国-三网双向优化-mini版（限量）", price=Decimal("45.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=211", in_stock=False, location="伦敦", line_tags=['9929', '三网优化'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=500, port_mbps=100),
    RawProduct(external_id="207", name="英国-三网双向优化", price=Decimal("60.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=207", in_stock=False, location="伦敦", line_tags=['9929', '三网优化'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="204", name="英国-三网双向优化2核2G内存", price=Decimal("120.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=204", in_stock=False, location="伦敦", line_tags=['9929', '三网优化'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=None, bandwidth_gb=1500, port_mbps=400),
    RawProduct(external_id="194", name="德国原生IP（新IP补货）", price=Decimal("60.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=194", in_stock=False, location="德国", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=None, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="205", name="德国原生IP - 高配置", price=Decimal("100.00"), currency="CNY", billing_cycle="monthly", purchase_url="https://666clouds.com/cart.php?a=add&pid=205", in_stock=False, location="德国", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=None, bandwidth_gb=2000, port_mbps=1000),
]


class SixSixYunCrawler(MerchantCrawler):
    slug = "66yun"
    name = "66云"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://666clouds.com"
    aff_url_template = "https://666clouds.com/cart.php?a=add&pid={pid}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        live = _fetch_live(client)
        if len(live) >= 5:
            print(f"[66yun] live catalog: {len(live)} products from store pages")
            return live

        print(f"[66yun] store pages fallback to {len(PRESET_66YUN_PRODUCTS)} presets")
        return [
            RawProduct(
                external_id=p.external_id,
                name=p.name,
                price=p.price,
                currency=p.currency,
                billing_cycle=p.billing_cycle,
                price_options=list(p.price_options or []),
                purchase_url=p.purchase_url,
                in_stock=p.in_stock,
                location=p.location,
                line_tags=list(p.line_tags),
                cpu_cores=p.cpu_cores,
                ram_gb=p.ram_gb,
                disk_gb=p.disk_gb,
                bandwidth_gb=p.bandwidth_gb,
                port_mbps=p.port_mbps,
                from_preset=True,
            )
            for p in PRESET_66YUN_PRODUCTS
        ]
