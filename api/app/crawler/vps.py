"""V.PS (xTom 旗下高端 VPS 品牌) 适配器。
官网 https://v.ps，订购系统为 HostBill (https://vps.hosting)。

数据全部实时化：逐机房分类页解析套餐卡片（HostBill categories_boxes 模板），
名称、多周期价格、CPU/内存/硬盘/流量、库存（卡片 outofstock 标记）均来自官网当前页面；
端口速率页面未展示，沿用知识库标注。分类页不可达时回退预置数据 + 加购页库存校验，
保证商家改版或网络抖动时服务仍可用。
"""

from decimal import Decimal
import re

import httpx
from selectolax.parser import HTMLParser

from .base import (
    MerchantCrawler,
    RawProduct,
    normalize_line_tags,
    normalize_location,
)

BASE = "https://vps.hosting"

# 机房分类页：slug → (中文机房, 线路标签, 默认端口 Mbps)
# 端口速率为官方产品页公开标注（分类页未展示），按系列沿用知识库值
CATEGORIES: list[tuple[str, str, list[str], int]] = [
    ("tokyo-cloud-kvm-vps", "日本东京", ["CN2 GIA", "9929"], 1000),
    ("osaka-cloud-kvm-vps", "日本大阪", ["9929"], 1000),
    ("san-jose-cloud-kvm-vps", "美国圣何塞", ["CN2 GIA", "9929", "CMIN2"], 1000),
    ("hong-kong-cloud-kvm-vps", "香港", ["CMIN2"], 1000),
    ("frankfurt-cloud-kvm-vps", "德国法兰克福", ["9929"], 1000),
    ("duesseldorf-cloud-kvm-vps", "德国杜塞尔多夫", ["9929"], 1000),
    ("amsterdam-cloud-kvm-vps", "荷兰阿姆斯特丹", ["9929"], 1000),
    ("london-cloud-kvm-vps", "英国伦敦", ["9929"], 1000),
    ("tallinn-cloud-kvm-vps", "爱沙尼亚塔林", ["9929"], 1000),
    ("sydney-cloud-kvm-vps", "澳大利亚悉尼", ["9929"], 1000),
    ("newyork-cloud-kvm-vps", "美国纽约", ["普通BGP"], 1000),
    ("seattle-cloud-kvm-vps", "美国西雅图", ["普通BGP"], 1000),
]

# 每个机房/系列的代表性 PID：HostBill 加购页天然输出该分类下的所有套餐卡片及实时库存/多周期价格
# 相比伪静态 /cart/<slug>/（易被 Cloudflare WAF 挑战），加购页端点能够直接稳定穿透
# (pid, 机房规范中文名, 线路标签, 默认端口速率 Mbps)
REPRESENTATIVE_PIDS: list[tuple[str, str, list[str], int]] = [
    # 日本东京
    ("148", "日本东京", ["CN2 GIA", "9929"], 1000),  # Tokyo Cloud KVM
    ("164", "日本东京", ["CN2 GIA", "9929"], 500),   # Tokyo Mini Pro
    ("259", "日本东京", ["普通BGP"], 1000),           # Tokyo EPYC Gen 2
    # 日本大阪
    ("140", "日本大阪", ["9929"], 1000),             # Osaka Cloud KVM
    ("268", "日本大阪", ["普通BGP"], 1000),           # Osaka Edge
    # 美国圣何塞
    ("144", "美国圣何塞", ["CN2 GIA", "9929", "CMIN2"], 1000),  # SJC Cloud KVM
    ("163", "美国圣何塞", ["CN2 GIA", "9929", "CMIN2"], 500),   # SJC Mini Pro
    # 香港
    ("286", "香港", ["CMIN2"], 1000),                # HKG Cloud KVM
    # 德国法兰克福
    ("118", "德国法兰克福", ["9929"], 1000),         # FRA Cloud KVM
    ("169", "德国法兰克福", ["9929"], 500),          # FRA Mini Pro
    ("194", "德国法兰克福", ["9929"], 1000),         # FRA Nano
    # 德国杜塞尔多夫
    ("104", "德国杜塞尔多夫", ["9929"], 1000),       # DUS Cloud KVM
    # 荷兰阿姆斯特丹
    ("91", "荷兰阿姆斯特丹", ["9929"], 1000),        # AMS Cloud KVM
    ("184", "荷兰阿姆斯特丹", ["9929"], 1000),       # AMS Nano
    # 英国伦敦
    ("135", "英国伦敦", ["9929"], 1000),             # LON Cloud KVM
    # 爱沙尼亚塔林
    ("122", "爱沙尼亚塔林", ["9929"], 1000),         # TLL Cloud KVM
    # 澳大利亚悉尼
    ("152", "澳大利亚悉尼", ["9929"], 1000),         # SYD Cloud KVM
    ("167", "澳大利亚悉尼", ["9929"], 500),          # SYD Mini Pro
    # 新加坡
    ("250", "新加坡", ["普通BGP"], 1000),           # SIN Edge
    ("235", "新加坡", ["普通BGP"], 1000),           # SIN EPYC
    # 美国纽约
    ("127", "美国纽约", ["普通BGP"], 1000),           # NYC Cloud KVM
    # 美国西雅图
    ("131", "美国西雅图", ["普通BGP"], 1000),         # SEA Cloud KVM
]

# 档位中文映射：页面只有英文档位，补中文提高可读性（未识别档位原样保留）
_TIER_CN = {
    "starter": "入门", "essential": "基础", "pro": "进阶", "premium": "高配",
    "ultra": "顶配", "edge": "轻量", "storage": "存储",
}

_CYCLE_MAP = {
    "m": "monthly",
    "q": "quarterly",
    "s": "semi_annually",
    "a": "annually",
    "b": "biennially",
    "t": "triennially",
    "p4": "p4",
    "p5": "p5",
}

_RE_PRICE = re.compile(r"([€$£])?\s*(\d+(?:\.\d{1,2})?)\s*(EUR|USD|GBP)?", re.I)
_CURRENCY_MAP = {"€": "EUR", "$": "USD", "£": "GBP"}
_RE_GB = re.compile(r"(\d+(?:\.\d+)?)\s*(GB|TB)", re.I)


def _gb(text: str) -> int | None:
    """'1 TB' → 1000，'0.5 TB' → 500，'20 GB' → 20（GB 单位 1024 进制不适用，按运营商千进制惯例）"""
    m = _RE_GB.search(text)
    if not m:
        return None
    v = float(m.group(1))
    return round(v * 1000) if m.group(2).upper() == "TB" else round(v)


def _tier_name(plan: str) -> str:
    """'Pro' → '进阶 Pro'，'Ultra 16C' → '顶配 Ultra 16C'"""
    cleaned = re.sub(
        r"^(?:tokyo|osaka|san jose|hong kong|frankfurt|dusseldorf|duesseldorf|amsterdam|london|sydney|new york|seattle|singapore)\s+",
        "",
        plan,
        flags=re.I,
    ).strip()
    first = cleaned.split()[0].lower() if cleaned else ""
    cn = _TIER_CN.get(first)
    return f"{cn} {cleaned}" if cn else cleaned


def _parse_card(card, location: str, line_tags: list[str], port_mbps: int) -> RawProduct | None:
    pid = (card.attributes.get("data-value") or "").strip()
    name_node = card.css_first("h4")
    if not pid or not name_node:
        return None
    plan = name_node.text(strip=True)
    if not plan:
        return None

    # 多周期价格：product-price cycle-x
    price_options: list[dict] = []
    for sp in card.css(".product-price"):
        cls = sp.attributes.get("class", "") or ""
        m = re.search(r"cycle-(\w+)", cls)
        pm = _RE_PRICE.search(sp.text(strip=True))
        if not m or not pm:
            continue
        cycle = _CYCLE_MAP.get(m.group(1))
        if not cycle:
            continue
        price_options.append({
            "billing_cycle": cycle,
            "price": float(pm.group(2)),
            "currency": (pm.group(3) or _CURRENCY_MAP.get(pm.group(1) or "", "EUR")).upper(),
            "purchase_url": f"{BASE}/?cmd=cart&action=add&id={pid}",
        })
    if not price_options:
        return None

    # 规格行：text-muted 标签 + 相邻 bold 值
    cpu = ram = disk = bw = None
    for label in card.css(".text-muted"):
        key = label.text(strip=True).lower()
        val_node = label.parent.css_first(".font-weight-bold")
        if not val_node:
            continue
        val = val_node.text(strip=True)
        if key == "cpu":
            if m := re.search(r"(\d+)", val):
                cpu = int(m.group(1))
        elif key == "memory":
            if m := re.search(r"(\d+(?:\.\d+)?)", val):
                ram = Decimal(m.group(1))
        elif "storage" in key:
            disk = _gb(val)
        elif "transfer" in key:
            bw = _gb(val)

    # 库存：卡片 class 含 outofstock 即缺货
    in_stock = "outofstock" not in (card.attributes.get("class", "") or "")

    # 名称规范化：机房缩写 + 中文档位（如 NRT 进阶 Pro），与前端短名称规则兼容
    loc_prefix = {
        "日本东京": "NRT", "日本大阪": "KIX", "美国圣何塞": "SJC", "香港": "HKG",
        "德国法兰克福": "FRA", "德国杜塞尔多夫": "DUS", "荷兰阿姆斯特丹": "AMS",
        "英国伦敦": "LON", "爱沙尼亚塔林": "TLL", "澳大利亚悉尼": "SYD",
        "美国纽约": "NYC", "美国西雅图": "SEA", "新加坡": "SIN",
    }.get(location, location)

    # 首选月付价作为基准价（V.PS 主打月付性能机）
    base = next((o for o in price_options if o["billing_cycle"] == "monthly"), price_options[0])

    return RawProduct(
        external_id=pid,
        name=f"{loc_prefix} {_tier_name(plan)}",
        price=Decimal(str(base["price"])),
        currency=base["currency"],
        billing_cycle=base["billing_cycle"],
        price_options=price_options,
        purchase_url=f"{BASE}/?cmd=cart&action=add&id={pid}",
        in_stock=in_stock,
        location=location,
        line_tags=list(line_tags),
        cpu_cores=cpu,
        ram_gb=ram,
        disk_gb=disk,
        bandwidth_gb=bw,
        port_mbps=port_mbps,
        from_preset=False,
        stock_verified=True,
    )


def _fetch_live(client: httpx.Client) -> list[RawProduct]:
    results: list[RawProduct] = []
    seen_keys: set[tuple[str, str]] = set()
    consecutive_blocked = 0

    # 1. 访问商城根目录进行会话预热（建立真实的 HostBill SESSID / cookies）
    try:
        client.get(f"{BASE}/")
    except Exception:
        pass

    # 2. 逐分类请求代表性 PID 的加购端点
    # HostBill 加购页天然会同时完整输出该分类下的所有套餐卡片及实时库存/价格，
    # 相比伪静态路由 /cart/{slug}/，原生加购端点不易触发 Cloudflare 403 挑战。
    for pid, location, line_tags, port in REPRESENTATIVE_PIDS:
        try:
            resp = client.get(f"{BASE}/?cmd=cart&action=add&id={pid}")
            if resp.status_code == 403:
                consecutive_blocked += 1
                if consecutive_blocked >= 2 and not results:
                    print(f"[vps] Cloudflare 403 blocked ({consecutive_blocked} consecutive) on pid {pid}, breaking early")
                    break
                continue
            resp.raise_for_status()
            consecutive_blocked = 0
        except Exception as e:
            consecutive_blocked += 1
            print(f"[vps] category pid {pid} fetch failed: {e}")
            if consecutive_blocked >= 2 and not results:
                print(f"[vps] consecutive failures on categories, fast-failing live crawl")
                break
            continue

        tree = HTMLParser(resp.text)
        for card in tree.css(".cart-product[data-value]"):
            card_pid = card.attributes.get("data-value", "").strip()
            key = (location, card_pid)
            if card_pid and key in seen_keys:
                continue
            p = _parse_card(card, location, line_tags, port)
            if p:
                if card_pid:
                    seen_keys.add(key)
                results.append(p)
    return results


# ── 预置数据（分类页整体不可达时的回退）──
# 仅保留核心字段，库存会以加购页 var errors 信号再校验
PRESET_VPS_PRODUCTS: list[RawProduct] = [
    RawProduct(external_id="164", name="NRT Mini Pro", price=Decimal("49.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=164", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=500),
    RawProduct(external_id="148", name="NRT 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=148", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="149", name="NRT 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=149", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="150", name="NRT 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=150", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="163", name="SJC Mini Pro", price=Decimal("49.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=163", in_stock=False, location="圣何塞", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=500),
    RawProduct(external_id="144", name="SJC 入门 Starter", price=Decimal("8.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=144", in_stock=False, location="圣何塞", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="145", name="SJC 基础 Essential", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=145", in_stock=False, location="圣何塞", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="146", name="SJC 进阶 Pro", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=146", in_stock=False, location="圣何塞", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="286", name="HKG 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=286", in_stock=False, location="香港", line_tags=['CMIN2'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="287", name="HKG 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=287", in_stock=False, location="香港", line_tags=['CMIN2'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="288", name="HKG 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=288", in_stock=False, location="香港", line_tags=['CMIN2'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="140", name="KIX 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=140", in_stock=False, location="大阪", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="141", name="KIX 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=141", in_stock=False, location="大阪", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="142", name="KIX 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=142", in_stock=False, location="大阪", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="169", name="FRA Mini Pro (德国法兰克福 9929 精品专线年付)", price=Decimal("49.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=169", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=500),
    RawProduct(external_id="194", name="FRA Nano (德国法兰克福超值轻量年付神机)", price=Decimal("9.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=194", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="118", name="FRA 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=118", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="119", name="FRA 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=119", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="135", name="LON 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=135", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="136", name="LON 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=136", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="167", name="SYD Mini Pro (澳大利亚悉尼 9929 专线年付款)", price=Decimal("49.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=167", in_stock=False, location="悉尼", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=500),
    RawProduct(external_id="152", name="SYD 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=152", in_stock=False, location="悉尼", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="184", name="AMS Nano (荷兰阿姆斯特丹超值轻量年付款)", price=Decimal("9.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=184", in_stock=False, location="阿姆斯特丹", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="91", name="AMS 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=91", in_stock=False, location="阿姆斯特丹", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="250", name="SIN Edge Green (新加坡 AMD EPYC 2G 内存 1Gbps)", price=Decimal("15.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=250", in_stock=False, location="新加坡", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1024, port_mbps=1000),
    RawProduct(external_id="151", name="NRT 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=151", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="207", name="NRT 顶配 Ultra", price=Decimal("39.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=207", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=8, ram_gb=Decimal("16.0"), disk_gb=160, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="283", name="NRT 顶配 Ultra 16C", price=Decimal("59.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=283", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=16, ram_gb=Decimal("16.0"), disk_gb=160, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="143", name="KIX 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=143", in_stock=False, location="大阪", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="147", name="SJC 高配 Premium", price=Decimal("39.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=147", in_stock=False, location="圣何塞", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="289", name="HKG 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=289", in_stock=False, location="香港", line_tags=['CMIN2'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="120", name="FRA 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=120", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="121", name="FRA 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=121", in_stock=False, location="法兰克福", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="104", name="DUS 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=104", in_stock=False, location="杜塞尔多夫", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="112", name="DUS 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=112", in_stock=False, location="杜塞尔多夫", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="113", name="DUS 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=113", in_stock=False, location="杜塞尔多夫", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="114", name="DUS 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=114", in_stock=False, location="杜塞尔多夫", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="105", name="AMS 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=105", in_stock=False, location="阿姆斯特丹", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="106", name="AMS 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=106", in_stock=False, location="阿姆斯特丹", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="107", name="AMS 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=107", in_stock=False, location="阿姆斯特丹", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="137", name="LON 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=137", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="138", name="LON 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=138", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="122", name="TLL 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=122", in_stock=False, location="爱沙尼亚塔林", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="123", name="TLL 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=123", in_stock=False, location="爱沙尼亚塔林", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="124", name="TLL 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=124", in_stock=False, location="爱沙尼亚塔林", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="125", name="TLL 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=125", in_stock=False, location="爱沙尼亚塔林", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="153", name="SYD 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=153", in_stock=False, location="悉尼", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="154", name="SYD 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=154", in_stock=False, location="悉尼", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="155", name="SYD 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=155", in_stock=False, location="悉尼", line_tags=['9929'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="127", name="NYC 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=127", in_stock=False, location="纽约", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="128", name="NYC 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=128", in_stock=False, location="纽约", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="129", name="NYC 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=129", in_stock=False, location="纽约", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="130", name="NYC 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=130", in_stock=False, location="纽约", line_tags=['普通BGP'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="131", name="SEA 入门 Starter", price=Decimal("6.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=131", in_stock=False, location="西雅图", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="132", name="SEA 基础 Essential", price=Decimal("7.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=132", in_stock=False, location="西雅图", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="133", name="SEA 进阶 Pro", price=Decimal("9.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=133", in_stock=False, location="西雅图", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="134", name="SEA 高配 Premium", price=Decimal("19.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=134", in_stock=False, location="西雅图", line_tags=['普通BGP'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000),
    # 补充：东京 Mini / 大阪轻量 / 新加坡 EPYC / 东京 EPYC Gen 2
    RawProduct(external_id="161", name="NRT Mini Pro", price=Decimal("39.95"), currency="EUR", billing_cycle="annually", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=161", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=500),
    RawProduct(external_id="235", name="SIN EPYC Explorer", price=Decimal("46.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=235", in_stock=False, location="新加坡", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="236", name="SIN EPYC Enhancer", price=Decimal("84.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=236", in_stock=False, location="新加坡", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="237", name="SIN EPYC Enterprise", price=Decimal("169.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=237", in_stock=False, location="新加坡", line_tags=['普通BGP'], cpu_cores=8, ram_gb=Decimal("16.0"), disk_gb=160, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="238", name="SIN EPYC Elite", price=Decimal("329.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=238", in_stock=False, location="新加坡", line_tags=['普通BGP'], cpu_cores=16, ram_gb=Decimal("32.0"), disk_gb=320, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="259", name="NRT EPYC Flash Gen 2", price=Decimal("49.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=259", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="260", name="NRT EPYC Flow Gen 2", price=Decimal("95.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=260", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="261", name="NRT EPYC Fleet Gen 2", price=Decimal("191.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=261", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=8, ram_gb=Decimal("16.0"), disk_gb=160, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="262", name="NRT EPYC Formula Gen 2", price=Decimal("383.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=262", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=16, ram_gb=Decimal("32.0"), disk_gb=320, bandwidth_gb=8000, port_mbps=1000),
    RawProduct(external_id="268", name="KIX 轻量 Edge Green", price=Decimal("8.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=268", in_stock=False, location="大阪", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="270", name="KIX 轻量 Edge Blue", price=Decimal("17.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=270", in_stock=False, location="大阪", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="271", name="KIX 轻量 Edge Yellow", price=Decimal("39.55"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=271", in_stock=False, location="大阪", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("4.0"), disk_gb=60, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="272", name="KIX 轻量 Edge Orange", price=Decimal("69.95"), currency="EUR", billing_cycle="monthly", purchase_url="https://vps.hosting/?cmd=cart&action=add&id=272", in_stock=False, location="大阪", line_tags=['普通BGP'], cpu_cores=8, ram_gb=Decimal("8.0"), disk_gb=120, bandwidth_gb=8000, port_mbps=1000),
]

_RE_ERRORS = re.compile(r"var\s+errors\s*=\s*\[(.*?)\]", re.S | re.I)
_OOS_KEYWORDS = ("unavailable", "out of stock", "sold out")


def _inspect_product_by_pid(client: httpx.Client, pid: str) -> tuple[bool, list[dict], bool]:
    """加购页实时校验：精确检查对应 pid 卡片的真实库存与多周期价格。返回 (in_stock, price_options, is_error)"""
    try:
        r = client.get(f"{BASE}/?cmd=cart&action=add&id={pid}", timeout=10)
    except Exception:
        return False, [], True
    if r.status_code != 200:
        return False, [], True

    tree = HTMLParser(r.text)
    card = tree.css_first(f'[data-value="{pid}"]')
    if not card:
        m = _RE_ERRORS.search(r.text)
        if m and any(kw in m.group(1).lower() for kw in _OOS_KEYWORDS):
            return False, [], False
        return False, [], False

    # 1. 严格库存判定：卡片 class 包含 outofstock 或包含缺货徽章则判定缺货
    cls = card.attributes.get("class", "") or ""
    has_oos_badge = card.css_first(".product-out-of-stock, .cart-product-outofstock-badge") is not None
    in_stock = ("outofstock" not in cls) and not has_oos_badge

    # 2. 实时多周期价格解析（过滤 p4/p5 等 4~5 年非常规周期）
    price_options: list[dict] = []
    for sp in card.css(".product-price"):
        c_cls = sp.attributes.get("class", "") or ""
        m = re.search(r"cycle-(\w+)", c_cls)
        pm = _RE_PRICE.search(sp.text(strip=True))
        if not m or not pm:
            continue
        cycle = _CYCLE_MAP.get(m.group(1))
        if not cycle or cycle in ("p4", "p5"):
            continue
        price_options.append({
            "billing_cycle": cycle,
            "price": float(pm.group(2)),
            "currency": (pm.group(3) or _CURRENCY_MAP.get(pm.group(1) or "", "EUR")).upper(),
            "purchase_url": f"{BASE}/?cmd=cart&action=add&id={pid}",
        })

    return in_stock, price_options, False


_VPS_LOC_META = {
    "tokyo gen 2": ("日本东京", "NRT", ["普通BGP"], 1000),
    "tokyo": ("日本东京", "NRT", ["CN2 GIA", "9929"], 1000),
    "osaka edge": ("日本大阪", "KIX", ["普通BGP"], 1000),
    "osaka": ("日本大阪", "KIX", ["9929"], 1000),
    "san jose": ("美国圣何塞", "SJC", ["CN2 GIA", "9929", "CMIN2"], 1000),
    "hong kong": ("香港", "HKG", ["CMIN2"], 1000),
    "frankfurt": ("德国法兰克福", "FRA", ["9929"], 1000),
    "düsseldorf": ("德国杜塞尔多夫", "DUS", ["9929"], 1000),
    "duesseldorf": ("德国杜塞尔多夫", "DUS", ["9929"], 1000),
    "amsterdam": ("荷兰阿姆斯特丹", "AMS", ["9929"], 1000),
    "london": ("英国伦敦", "LON", ["9929"], 1000),
    "tallinn": ("爱沙尼亚塔林", "TLL", ["9929"], 1000),
    "sydney": ("澳大利亚悉尼", "SYD", ["9929"], 1000),
    "new york": ("美国纽约", "NYC", ["普通BGP"], 1000),
    "seattle": ("美国西雅图", "SEA", ["普通BGP"], 1000),
    "singapore": ("新加坡", "SIN", ["普通BGP"], 1000),
}


def _enrich_vps_product(dp: RawProduct) -> RawProduct:
    raw_name = dp.name
    loc_field = (dp.location or "").lower()
    name_lower = raw_name.lower()
    matched = None
    for k, v in _VPS_LOC_META.items():
        if k in loc_field or k in name_lower:
            matched = v
            break
    loc, pfx, lines, port = matched if matched else (dp.location, "", ["普通BGP"], 1000)
    clean = raw_name
    for k in _VPS_LOC_META:
        clean = re.sub(rf"\b{re.escape(k)}\b", "", clean, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip()
    tier = _tier_name(clean)
    final_name = f"{pfx} {tier}".strip() if pfx else tier
    return RawProduct(
        external_id=dp.external_id,
        name=final_name,
        price=dp.price,
        currency=dp.currency,
        billing_cycle=dp.billing_cycle,
        price_options=dp.price_options,
        purchase_url=f"{BASE}/?cmd=cart&action=add&id={dp.external_id}",
        in_stock=dp.in_stock,
        location=normalize_location(loc),
        line_tags=normalize_line_tags(final_name, lines),
        cpu_cores=dp.cpu_cores,
        ram_gb=dp.ram_gb,
        disk_gb=dp.disk_gb,
        bandwidth_gb=dp.bandwidth_gb,
        port_mbps=port or dp.port_mbps,
        stock_verified=True,
    )


def _fetch_dvps(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    try:
        from .dvps_source import DvpsSource
        dvps_prods = DvpsSource().fetch_products("vps", client)
        for dp in dvps_prods:
            products.append(_enrich_vps_product(dp))
    except Exception as e:
        print(f"[vps] dvps feed error: {e}")
    return products


class VPSCrawler(MerchantCrawler):
    slug = "vps"
    name = "V.PS"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://v.ps"
    crawl_method = "官方 HostBill 订购商城各机房分类页"
    aff_url_template = "{url}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        live = _fetch_live(client)
        if len(live) >= 10:
            print(f"[vps] live catalog: {len(live)} products from category pages")
            return live

        dvps = _fetch_dvps(client)
        if len(dvps) >= 10:
            print(f"[vps] live catalog: {len(dvps)} products from dvps source")
            return dvps

        # 回退：预置数据 + 加购页逐卡片库存与价格校验
        print(f"[vps] category pages and dvps unavailable ({len(live)} parsed), fallback to presets")
        results: list[RawProduct] = []
        consecutive_inspect_err = 0
        for p in PRESET_VPS_PRODUCTS:
            if consecutive_inspect_err >= 2:
                # 连续加购页请求报错或被盾拦截，中断后续 30+ 次网络请求，直接使用预置状态，防止扫描超时
                stock, opts = p.in_stock, list(p.price_options or [])
            else:
                stock, opts, is_err = _inspect_product_by_pid(client, p.external_id)
                if is_err:
                    consecutive_inspect_err += 1
                else:
                    consecutive_inspect_err = 0
            options = opts if opts else list(p.price_options or [])
            base_opt = next((o for o in options if o["billing_cycle"] == p.billing_cycle), None)
            if not base_opt and options:
                base_opt = options[0]
            price = Decimal(str(base_opt["price"])) if base_opt else p.price
            cycle = base_opt["billing_cycle"] if base_opt else p.billing_cycle
            currency = base_opt["currency"] if base_opt else p.currency

            results.append(
                RawProduct(
                    external_id=p.external_id,
                    name=p.name,
                    price=price,
                    currency=currency,
                    billing_cycle=cycle,
                    price_options=options,
                    purchase_url=p.purchase_url,
                    in_stock=stock,
                    location=normalize_location(p.location),
                    line_tags=normalize_line_tags(p.name, p.line_tags),
                    cpu_cores=p.cpu_cores,
                    ram_gb=p.ram_gb,
                    disk_gb=p.disk_gb,
                    bandwidth_gb=p.bandwidth_gb,
                    port_mbps=p.port_mbps,
                    from_preset=True,
                    stock_verified=True,
                )
            )
        return results
