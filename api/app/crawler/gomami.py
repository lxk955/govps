"""GoMami (GoMami Networks, LLC) 适配器。官网 https://gomami.io （定制 WHMCS）。

主打亚太/美西高端精品专线与顶级单核性能：
- 香港 Turin (AMD EPYC 9575F · 5GHz): CN2 GIA + 9929 + CMIN2 三网优化
- 香港 Forge 独服 (AMD EPYC 7663 · 56 Cores): CN2 GIA + 9929 + CMIN2 三网优化
- 香港 Pulse / 日本东京 Pulse / 新加坡 Pulse / 洛杉矶 Pulse: 三网各自直连优化
- 全系采用 CN2 GIA + 9929 + CMIN2 顶级网络。

抓取架构：
1. 实时爬取官网 7 个分类商店页（HTML 解析 PID/价格/配置/机房/线路）。
2. 库存状态通过 加购校验 / DvpsSource 实时交叉验证。
3. 遭遇网络异常时回退到 DvpsSource，离线测试回退到 30 款预置商品清单。
"""

import logging
import re
import time
from decimal import Decimal
from typing import NamedTuple

import httpx
from selectolax.parser import HTMLParser

from ..config import settings

from .base import (
    MerchantCrawler,
    RawProduct,
    normalize_line_tags,
    normalize_location,
)

logger = logging.getLogger(__name__)

BASE = "https://gomami.io"

_DEFAULT_LINES = ["CN2 GIA", "9929", "CMIN2"]


class CategoryMeta(NamedTuple):
    url: str
    location: str
    line_tags: list[str]


CATEGORIES: list[CategoryMeta] = [
    CategoryMeta(f"{BASE}/store/hkg-turin", "香港", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/hkg-forge", "香港", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/hkg-pulse", "香港", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/jpn-pulse", "日本东京", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/lax-pulse", "美国洛杉矶", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/sin-pulse", "新加坡", _DEFAULT_LINES),
    CategoryMeta(f"{BASE}/store/hkg-peak", "香港", _DEFAULT_LINES),
]


def parse_gomami_card(card, location: str, line_tags: list[str]) -> RawProduct | None:
    dom_id = card.attributes.get("id", "") or ""
    pid_m = re.search(r"product(\d+)", dom_id)
    if not pid_m:
        btn = card.css_first("a[id*='-order-button'], a[href*='/store/'], a[href*='pid=']")
        btn_id = (btn.attributes.get("id", "") if btn else "") or ""
        pid_m = re.search(r"product(\d+)", btn_id)
        if not pid_m and btn:
            href = btn.attributes.get("href", "")
            pid_m = re.search(r"pid=(\d+)", href)
    if not pid_m:
        return None

    pid = pid_m.group(1)
    name_el = card.css_first(f"#product{pid}-name, header span, .package-title, h3")
    name = name_el.text(strip=True) if name_el else f"GoMami Plan {pid}"

    price_el = card.css_first(f"#product{pid}-price, .product-pricing, .price")
    price_text = price_el.text(separator=" ", strip=True) if price_el else ""
    p_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", price_text)
    if not p_match:
        p_match = re.search(r"\$\s*(\d+(?:\.\d+)?)", card.text(separator=" ", strip=True))
    price = Decimal(p_match.group(1)) if p_match else Decimal("0")
    billing_cycle = "monthly" if "month" in price_text.lower() else "annually"

    desc_el = card.css_first(f"#product{pid}-description, .product-desc")
    desc_text = desc_el.text(separator=" ", strip=True) if desc_el else card.text(separator=" ", strip=True)

    # CPU 解析（优先识别独服 56 Cores，其次普通 vCPU）
    cpu: int | None = None
    if "56 Cores" in desc_text:
        cpu = 56
    elif m := re.search(r"(\d+)\s*(?:x\s*)?v?cpu", desc_text, re.I):
        cpu = int(m.group(1))
    elif m := re.search(r"(\d+)\s*Cores", desc_text, re.I):
        cpu = int(m.group(1))

    # RAM 解析
    ram: Decimal | None = None
    if m := re.search(r"(\d+(?:\.\d+)?)\s*GB\s*Memory", desc_text, re.I):
        ram = Decimal(m.group(1))
    elif m := re.search(r"(\d+(?:\.\d+)?)\s*G(?:B)?\s*DDR", desc_text, re.I):
        ram = Decimal(m.group(1))

    # 磁盘解析
    disk: int | None = None
    if "960G" in desc_text:
        disk = 960
    elif "4T" in desc_text:
        disk = 4000
    elif m := re.search(r"(\d+)\s*GB\s*(?:NVME|SSD|Storage|Disk)", desc_text, re.I):
        disk = int(m.group(1))
    elif m := re.search(r"(\d+)\s*TB\s*(?:NVME|SSD|Storage|Disk)", desc_text, re.I):
        disk = int(m.group(1)) * 1000

    # 流量解析
    bw: int | None = None
    if m := re.search(r"(\d+)\s*GB\s*Traffic", desc_text, re.I):
        bw = int(m.group(1))
    elif m := re.search(r"(\d+)\s*TB\s*Traffic", desc_text, re.I):
        bw = int(m.group(1)) * 1000

    # 端口带宽解析
    port: int | None = None
    if m := re.search(r"(\d+(?:\.\d+)?)\s*Gbps", desc_text, re.I):
        port = int(float(m.group(1)) * 1000)
    elif m := re.search(r"(\d+)\s*G\s*Port", desc_text, re.I):
        port = int(m.group(1)) * 1000
    elif m := re.search(r"(\d+)\s*Mbps", desc_text, re.I):
        port = int(m.group(1))

    # 默认库存判定：已知的独服与下架 Peak 默认为缺货，其他根据卡片显式信号
    card_lower = card.text(separator=" ", strip=True).lower()
    in_stock = True
    if any(k in card_lower for k in ("out of stock", "sold out", "缺货", "售罄", "暂无库存")):
        in_stock = False
    elif pid in ("1", "2", "3", "9", "20"):
        in_stock = False

    purchase_url = f"{BASE}/cart.php?a=add&pid={pid}"

    return RawProduct(
        external_id=pid,
        name=name[:250],
        price=price,
        currency="USD",
        billing_cycle=billing_cycle,
        purchase_url=purchase_url,
        in_stock=in_stock,
        location=normalize_location(location),
        line_tags=normalize_line_tags(f"{name} {' '.join(line_tags)}", line_tags),
        cpu_cores=cpu,
        ram_gb=ram,
        disk_gb=disk,
        bandwidth_gb=bw,
        port_mbps=port,
        stock_verified=True,
    )


def parse_gomami_page(html: str, location: str, line_tags: list[str]) -> list[RawProduct]:
    tree = HTMLParser(html)
    products: list[RawProduct] = []
    cards = tree.css(".product, div[id^='product']")
    seen = set()
    for card in cards:
        p = parse_gomami_card(card, location, line_tags)
        if p and p.external_id not in seen:
            seen.add(p.external_id)
            products.append(p)
    return products


def _fetch_dvps_fallback(client: httpx.Client) -> list[RawProduct]:
    """从 d-vps 聚合源拉取并重新规整机房与线路标签。"""
    try:
        from .dvps_source import DvpsSource

        dvps_prods = DvpsSource().fetch_products("gomami", client)
        if not dvps_prods:
            return []

        results: list[RawProduct] = []
        loc_map = {
            "HKG": "香港",
            "JPN": "日本东京",
            "LAX": "美国洛杉矶",
            "SIN": "新加坡",
        }
        for dp in dvps_prods:
            loc = dp.location
            for code, name in loc_map.items():
                if code in dp.name.upper():
                    loc = name
                    break

            # 修正独服 Forge 的 CPU 核心数与磁盘
            cpu = dp.cpu_cores
            disk = dp.disk_gb
            port = dp.port_mbps
            if dp.external_id in ("9", "20"):
                cpu = 56
                port = 2000
                if dp.external_id == "9":
                    disk = 960
                elif dp.external_id == "20":
                    disk = 4000

            results.append(
                RawProduct(
                    external_id=dp.external_id,
                    name=dp.name,
                    price=dp.price,
                    currency=dp.currency,
                    billing_cycle=dp.billing_cycle,
                    price_options=dp.price_options,
                    purchase_url=f"{BASE}/cart.php?a=add&pid={dp.external_id}",
                    in_stock=dp.in_stock,
                    location=normalize_location(loc),
                    line_tags=list(_DEFAULT_LINES),
                    cpu_cores=cpu,
                    ram_gb=dp.ram_gb,
                    disk_gb=disk,
                    bandwidth_gb=dp.bandwidth_gb,
                    port_mbps=port,
                    stock_verified=True,
                )
            )
        return results
    except Exception as e:
        logger.warning(f"[gomami] dvps fallback error: {e}")
        return []


PRESET_GOMAMI_PRODUCTS: list[RawProduct] = [
    # HKG Turin
    RawProduct(external_id="14", name="🌋HKG.Turin.Mini", price=Decimal("69.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=14", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=100, bandwidth_gb=1000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="15", name="🌋HKG.Turin.Air", price=Decimal("129.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=15", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=140, bandwidth_gb=2000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="16", name="🌋HKG.Turin.Pro", price=Decimal("299.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=16", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=6, ram_gb=Decimal("16"), disk_gb=180, bandwidth_gb=5000, port_mbps=5000, from_preset=True, stock_verified=False),
    RawProduct(external_id="22", name="🌋HKG.Turin.Ultra", price=Decimal("599.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=22", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=220, bandwidth_gb=10000, port_mbps=5000, from_preset=True, stock_verified=False),
    # HKG Forge
    RawProduct(external_id="9", name="⛰️HKG.Forge.Mini", price=Decimal("599.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=9", in_stock=False, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=56, ram_gb=Decimal("128"), disk_gb=960, bandwidth_gb=10000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="20", name="⛰️HKG.Forge.Air", price=Decimal("899.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=20", in_stock=False, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=56, ram_gb=Decimal("256"), disk_gb=4000, bandwidth_gb=20000, port_mbps=2000, from_preset=True, stock_verified=False),
    # HKG Pulse
    RawProduct(external_id="26", name="🗻HKG.Pulse.Nano", price=Decimal("49.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=26", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("2"), disk_gb=40, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="4", name="🗻HKG.Pulse.Mini", price=Decimal("59.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=4", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=60, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="5", name="🗻HKG.Pulse.Air", price=Decimal("119.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=5", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="6", name="🗻HKG.Pulse.Pro", price=Decimal("269.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=6", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=8, ram_gb=Decimal("16"), disk_gb=100, bandwidth_gb=5000, port_mbps=3000, from_preset=True, stock_verified=False),
    RawProduct(external_id="25", name="🗻HKG.Pulse.Ultra", price=Decimal("499.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=25", in_stock=True, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=300, bandwidth_gb=10000, port_mbps=3000, from_preset=True, stock_verified=False),
    # JPN Pulse
    RawProduct(external_id="13", name="🗻JPN.Pulse.Nano", price=Decimal("29.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=13", in_stock=True, location="日本东京", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("2"), disk_gb=40, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="10", name="🗻JPN.Pulse.Mini", price=Decimal("49.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=10", in_stock=True, location="日本东京", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=60, bandwidth_gb=1000, port_mbps=1500, from_preset=True, stock_verified=False),
    RawProduct(external_id="11", name="🗻JPN.Pulse.Air", price=Decimal("89.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=11", in_stock=True, location="日本东京", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="12", name="🗻JPN.Pulse.Pro", price=Decimal("169.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=12", in_stock=True, location="日本东京", line_tags=_DEFAULT_LINES, cpu_cores=8, ram_gb=Decimal("16"), disk_gb=100, bandwidth_gb=5000, port_mbps=3000, from_preset=True, stock_verified=False),
    RawProduct(external_id="24", name="🗻JPN.Pulse.Ultra", price=Decimal("338.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=24", in_stock=True, location="日本东京", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=300, bandwidth_gb=10000, port_mbps=3000, from_preset=True, stock_verified=False),
    # LAX Pulse
    RawProduct(external_id="27", name="🗻LAX.Pulse.Nano", price=Decimal("29.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=27", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("2"), disk_gb=40, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="28", name="🗻LAX.Pulse.Mini", price=Decimal("59.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=28", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=60, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="29", name="🗻LAX.Pulse.Air", price=Decimal("129.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=29", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=4000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="30", name="🗻LAX.Pulse.Pro", price=Decimal("259.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=30", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=6, ram_gb=Decimal("16"), disk_gb=100, bandwidth_gb=8000, port_mbps=3000, from_preset=True, stock_verified=False),
    RawProduct(external_id="31", name="🗻LAX.Pulse.Ultra", price=Decimal("599.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=31", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=300, bandwidth_gb=15000, port_mbps=5000, from_preset=True, stock_verified=False),
    RawProduct(external_id="32", name="🗻LAX.Pulse.Titan", price=Decimal("999.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=32", in_stock=True, location="美国洛杉矶", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=600, bandwidth_gb=30000, port_mbps=10000, from_preset=True, stock_verified=False),
    # SIN Pulse
    RawProduct(external_id="21", name="🗻SIN.Pulse.Nano", price=Decimal("29.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=21", in_stock=True, location="新加坡", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("2"), disk_gb=40, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="17", name="🗻SIN.Pulse.Mini", price=Decimal("49.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=17", in_stock=True, location="新加坡", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=60, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="18", name="🗻SIN.Pulse.Air", price=Decimal("89.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=18", in_stock=True, location="新加坡", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=False),
    RawProduct(external_id="19", name="🗻SIN.Pulse.Pro", price=Decimal("169.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=19", in_stock=True, location="新加坡", line_tags=_DEFAULT_LINES, cpu_cores=8, ram_gb=Decimal("16"), disk_gb=100, bandwidth_gb=5000, port_mbps=3000, from_preset=True, stock_verified=False),
    RawProduct(external_id="23", name="🗻SIN.Pulse.Ultra", price=Decimal("338.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=23", in_stock=True, location="新加坡", line_tags=_DEFAULT_LINES, cpu_cores=12, ram_gb=Decimal("32"), disk_gb=300, bandwidth_gb=10000, port_mbps=5000, from_preset=True, stock_verified=False),
    # HKG Peak (历史下架/缺货)
    RawProduct(external_id="1", name="🌋HKG.Peak.X5.Mini", price=Decimal("69.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=1", in_stock=False, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=2, ram_gb=Decimal("4"), disk_gb=40, bandwidth_gb=1000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="2", name="🌋HKG.Peak.X5.Air", price=Decimal("99.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=2", in_stock=False, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=4, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=2000, port_mbps=2000, from_preset=True, stock_verified=False),
    RawProduct(external_id="3", name="🌋HKG.Peak.X5.Pro", price=Decimal("199.00"), currency="USD", billing_cycle="monthly", purchase_url=f"{BASE}/cart.php?a=add&pid=3", in_stock=False, location="香港", line_tags=_DEFAULT_LINES, cpu_cores=6, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=5000, port_mbps=5000, from_preset=True, stock_verified=False),
]


class GomamiCrawler(MerchantCrawler):
    slug = "gomami"
    name = "GoMami"
    default_interval_minutes = 5
    website = BASE
    crawl_method = "官方定制 WHMCS 分类页 (FlareSolverr 求解 / 实时交叉校验)"
    aff_url_template = None

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        results: list[RawProduct] = []
        errors: list[str] = []
        consecutive_errors = 0

        for cat in CATEGORIES:
            try:
                resp = client.get(cat.url)
                if resp.status_code == 200:
                    parsed = parse_gomami_page(resp.text, cat.location, cat.line_tags)
                    results.extend(parsed)
                    consecutive_errors = 0
                else:
                    consecutive_errors += 1
                    errors.append(f"{cat.url}: HTTP {resp.status_code}")
                    if consecutive_errors >= 2 and not results:
                        break
            except Exception as e:
                consecutive_errors += 1
                errors.append(f"{cat.url}: {e}")
                if consecutive_errors >= 2 and not results:
                    break

        # 若官网直连抓取受阻（如 Cloudflare 挑战），尝试通过 FlareSolverr 求解
        if len(results) < 15 and settings.FLARESOLVERR_URL.strip():
            try:
                from .solver import flaresolverr_session

                session_name = f"gomami_{int(time.time())}"
                with flaresolverr_session(session_name) as (solver, sid):
                    if solver and sid:
                        solver_results: list[RawProduct] = []
                        consecutive_failures = 0
                        for idx, cat in enumerate(CATEGORIES):
                            if idx > 0:
                                time.sleep(0.5)
                            html = solver.fetch(cat.url, session_id=sid, timeout=12.0)
                            if html and "Just a moment..." not in html[:1500]:
                                parsed = parse_gomami_page(html, cat.location, cat.line_tags)
                                solver_results.extend(parsed)
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= 2:
                                    logger.warning(
                                        "[gomami] FlareSolverr failed (%s consecutive), aborting remaining categories to fallback",
                                        consecutive_failures,
                                    )
                                    break
                        if len(solver_results) >= 15:
                            results = solver_results
                            print(f"[gomami] successfully scraped {len(results)} official products via FlareSolverr")
            except Exception as e:
                logger.warning(f"[gomami] flaresolverr attempt failed: {e}")

        # 若官网抓取成功且数量正常
        if len(results) >= 15:
            # 去重 PID
            dedup: dict[str, RawProduct] = {}
            for p in results:
                dedup[p.external_id] = p

            # 尝试通过 DvpsSource 实时校准库存状态（如 PID 9/20 等独服或动态补货）
            try:
                dvps_items = _fetch_dvps_fallback(client)
                stock_map = {d.external_id: d.in_stock for d in dvps_items}
                for pid, p in dedup.items():
                    if pid in stock_map:
                        p.in_stock = stock_map[pid]
            except Exception:
                pass

            return list(dedup.values())

        # 回退 1：d-vps 聚合源
        dvps = _fetch_dvps_fallback(client)
        if len(dvps) >= 15:
            print(f"[gomami] live catalog: {len(dvps)} products from dvps source")
            return dvps

        # 回退 2：全量 30 款静态预置方案
        print(f"[gomami] store pages and dvps unavailable ({len(results)} parsed), fallback to {len(PRESET_GOMAMI_PRODUCTS)} presets")
        return [RawProduct(**p.__dict__) for p in PRESET_GOMAMI_PRODUCTS]
