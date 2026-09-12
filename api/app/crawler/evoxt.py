"""Evoxt 适配器。官网 https://evoxt.com，价格页 https://evoxt.com/pricing/。

主打全球多机房弹性部署与超高主频 CPU（最高 6.0 GHz）：
1. Standard Network (标准网络):
   覆盖美西/美东/英国/加拿大/德国/波兰/荷兰/日本东京/马来西亚/澳大利亚 9 大地区自由迁移。
2. Premium Network (优质网络):
   覆盖中国香港与日本大阪，优化直连 BGP。
3. Premium Plus Network (顶级三网优质网络):
   覆盖马来西亚（吉隆坡/赛城），集成 CTG GIA + 9929 + CMI 顶级回国优化线路。

抓取架构：
1. 实时抓取官网公开透明价格表 https://evoxt.com/pricing/。
2. 遭遇网络异常时回退到 d-vps 聚合源校准。
3. 离线测试与极端网络中断时回退至 33 款静态预置商品清单。
"""

import logging
import re
from decimal import Decimal

import httpx
from selectolax.parser import HTMLParser

from .base import (
    MerchantCrawler,
    RawProduct,
    normalize_line_tags,
    normalize_location,
)

logger = logging.getLogger(__name__)

BASE = "https://evoxt.com"
PRICING_URL = "https://evoxt.com/pricing/"
AFF_DEPLOY_URL = "https://console.evoxt.com/aff.php?aff=4675"

# 标准网络 PID 映射，与 d-vps.com 历史 PID (1..9) 严格保持 1:1 对齐
STANDARD_PIDS: dict[str, str] = {
    "VM-0.5": "1",
    "VM-0.75": "2",
    "VM-1": "3",
    "VM-1.5": "4",
    "VM-2": "5",
    "VM-3": "6",
    "VM-4": "7",
    "VM-6": "8",
    "VM-8": "9",
    "VM-12": "10",
    "VM-16": "11",
}

SECTION_CONFIGS = [
    {
        "table_idx": 0,
        "section_name": "Standard",
        "location": "多机房 (可迁)",
        "line_tags": ["普通BGP"],
        "id_prefix": "",
        "name_fmt": "{plan}",
    },
    {
        "table_idx": 1,
        "section_name": "Premium Network",
        "location": "香港 / 大阪",
        "line_tags": ["普通BGP"],
        "id_prefix": "hk-prem-",
        "name_fmt": "香港/大阪（优质网络）-{plan}",
    },
    {
        "table_idx": 2,
        "section_name": "Premium Plus Network",
        "location": "吉隆坡",
        "line_tags": ["CN2 GIA", "9929", "CMI"],
        "id_prefix": "my-prem-",
        "name_fmt": "马来西亚（优质网络）-{plan}",
    },
]


def parse_evoxt_pricing_page(html: str) -> list[RawProduct]:
    """解析 evoxt.com/pricing/ 页面中的 3 大网络体系价格表。"""
    tree = HTMLParser(html)
    blocks = tree.css("section.region-block")
    if not blocks:
        tables = tree.css("table")
    else:
        tables = [b.css_first("table") for b in blocks if b.css_first("table")]

    products: list[RawProduct] = []

    for cfg in SECTION_CONFIGS:
        idx = cfg["table_idx"]
        if idx >= len(tables) or not tables[idx]:
            continue
        tbl = tables[idx]

        for row in tbl.css("tr"):
            cols = [c.text(strip=True) for c in row.css("td, th")]
            if not cols or cols[0].lower() in ("plan", "套餐") or len(cols) < 7:
                continue

            plan_name = cols[0]
            cpu_text = cols[1]
            ram_text = cols[2]
            disk_text = cols[3]
            bw_text = cols[4]
            price_text = cols[6]

            # 核心数
            cpu = 1
            if m := re.search(r"(\d+)", cpu_text):
                cpu = int(m.group(1))

            # 内存 (GB)
            ram_gb = None
            if "gb" in ram_text.lower():
                if m := re.search(r"(\d+(?:\.\d+)?)", ram_text):
                    ram_gb = Decimal(m.group(1))
            elif "mb" in ram_text.lower():
                if m := re.search(r"(\d+)", ram_text):
                    ram_gb = (Decimal(m.group(1)) / 1024).quantize(Decimal("0.1"))

            # 磁盘 (GB)
            disk = 0
            if m := re.search(r"(\d+)", disk_text):
                disk = int(m.group(1))
                if "tb" in disk_text.lower():
                    disk *= 1000

            # 月流量 (GB)
            bw = 0
            if m := re.search(r"(\d+(?:\.\d+)?)", bw_text):
                val = float(m.group(1))
                bw = int(val * 1000 if "tb" in bw_text.lower() else val)

            # 月付价格
            price_val = Decimal("0.00")
            if m := re.search(r"(\d+\.\d+|\d+)", price_text):
                price_val = Decimal(m.group(1))

            # 唯一 external_id
            id_pfx = cfg["id_prefix"]
            if id_pfx:
                plan_key = plan_name.lower().replace("vm-", "")
                ext_id = f"{id_pfx}{plan_key}"
            else:
                ext_id = STANDARD_PIDS.get(plan_name, plan_name.lower())

            prod_name = cfg["name_fmt"].format(plan=plan_name)

            p = RawProduct(
                external_id=ext_id,
                name=prod_name,
                price=price_val,
                currency="USD",
                billing_cycle="monthly",
                purchase_url=AFF_DEPLOY_URL,
                in_stock=True,
                location=normalize_location(cfg["location"]),
                line_tags=normalize_line_tags(
                    f"{prod_name} {' '.join(cfg['line_tags'])}", cfg["line_tags"]
                ),
                cpu_cores=cpu,
                ram_gb=ram_gb,
                disk_gb=disk,
                bandwidth_gb=bw,
                port_mbps=1000,
                stock_verified=True,
            )
            products.append(p)

    return products


def _fetch_dvps_fallback(client: httpx.Client) -> list[RawProduct]:
    """从 d-vps 聚合源拉取标准网络套餐并补充完整规格。"""
    try:
        from .dvps_source import DvpsSource

        dvps_prods = DvpsSource().fetch_products("evoxt", client)
        if not dvps_prods:
            return []

        bw_map = {
            "1": 500,
            "2": 750,
            "3": 1000,
            "4": 1500,
            "5": 2000,
            "6": 3000,
            "7": 4000,
            "8": 5000,
            "9": 6000,
            "10": 8000,
            "11": 10000,
        }

        results: list[RawProduct] = []
        for dp in dvps_prods:
            pid = dp.external_id
            bw = dp.bandwidth_gb or bw_map.get(pid, 1000)
            results.append(
                RawProduct(
                    external_id=pid,
                    name=dp.name,
                    price=dp.price,
                    currency=dp.currency,
                    billing_cycle=dp.billing_cycle,
                    price_options=dp.price_options,
                    purchase_url=AFF_DEPLOY_URL,
                    in_stock=True,
                    location=normalize_location(dp.location or "多机房 (可迁)"),
                    line_tags=["普通BGP"],
                    cpu_cores=dp.cpu_cores,
                    ram_gb=dp.ram_gb,
                    disk_gb=dp.disk_gb,
                    bandwidth_gb=bw,
                    port_mbps=1000,
                    stock_verified=True,
                )
            )
        return results
    except Exception as e:
        logger.warning(f"[evoxt] dvps fallback error: {e}")
        return []


PRESET_EVOXT_PRODUCTS: list[RawProduct] = [
    # ── 1. Standard Network (标准网络，9 大区域自由迁) ──
    RawProduct(external_id="1", name="VM-0.5", price=Decimal("2.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("0.5"), disk_gb=5, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2", name="VM-0.75", price=Decimal("4.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("1"), disk_gb=10, bandwidth_gb=750, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="3", name="VM-1", price=Decimal("5.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="4", name="VM-1.5", price=Decimal("6.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=2, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=1500, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="5", name="VM-2", price=Decimal("11.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=2, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="6", name="VM-3", price=Decimal("14.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=4, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=3000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="7", name="VM-4", price=Decimal("23.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=4, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=4000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="8", name="VM-6", price=Decimal("29.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=8, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=5000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="9", name="VM-8", price=Decimal("47.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=8, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=6000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="10", name="VM-12", price=Decimal("60.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=16, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=8000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="11", name="VM-16", price=Decimal("95.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="多机房 (可迁)", line_tags=["普通BGP"], cpu_cores=16, ram_gb=Decimal("32"), disk_gb=100, bandwidth_gb=10000, port_mbps=1000, from_preset=True, stock_verified=True),

    # ── 2. Premium Network (中国香港与日本大阪优质直连) ──
    RawProduct(external_id="hk-prem-0.5", name="香港/大阪（优质网络）-VM-0.5", price=Decimal("2.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("0.5"), disk_gb=5, bandwidth_gb=250, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-0.75", name="香港/大阪（优质网络）-VM-0.75", price=Decimal("4.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("1"), disk_gb=10, bandwidth_gb=250, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-1", name="香港/大阪（优质网络）-VM-1", price=Decimal("5.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=1, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-1.5", name="香港/大阪（优质网络）-VM-1.5", price=Decimal("6.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=2, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=500, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-2", name="香港/大阪（优质网络）-VM-2", price=Decimal("11.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=2, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-3", name="香港/大阪（优质网络）-VM-3", price=Decimal("14.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=4, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-4", name="香港/大阪（优质网络）-VM-4", price=Decimal("23.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=4, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-6", name="香港/大阪（优质网络）-VM-6", price=Decimal("29.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=8, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-8", name="香港/大阪（优质网络）-VM-8", price=Decimal("47.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=8, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=3000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-12", name="香港/大阪（优质网络）-VM-12", price=Decimal("60.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=16, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=3000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="hk-prem-16", name="香港/大阪（优质网络）-VM-16", price=Decimal("95.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="香港 / 大阪", line_tags=["普通BGP"], cpu_cores=16, ram_gb=Decimal("32"), disk_gb=100, bandwidth_gb=5000, port_mbps=1000, from_preset=True, stock_verified=True),

    # ── 3. Premium Plus Network (马来西亚吉隆坡 CTG GIA + 9929 + CMI 顶级回国专线) ──
    RawProduct(external_id="my-prem-0.5", name="马来西亚（优质网络）-VM-0.5", price=Decimal("3.49"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=1, ram_gb=Decimal("0.5"), disk_gb=5, bandwidth_gb=150, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-0.75", name="马来西亚（优质网络）-VM-0.75", price=Decimal("4.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=1, ram_gb=Decimal("1"), disk_gb=10, bandwidth_gb=250, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-1", name="马来西亚（优质网络）-VM-1", price=Decimal("5.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=1, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=300, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-1.5", name="马来西亚（优质网络）-VM-1.5", price=Decimal("6.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=2, ram_gb=Decimal("2"), disk_gb=20, bandwidth_gb=300, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-2", name="马来西亚（优质网络）-VM-2", price=Decimal("11.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=2, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=600, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-3", name="马来西亚（优质网络）-VM-3", price=Decimal("14.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=4, ram_gb=Decimal("4"), disk_gb=30, bandwidth_gb=700, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-4", name="马来西亚（优质网络）-VM-4", price=Decimal("23.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=4, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=1000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-6", name="马来西亚（优质网络）-VM-6", price=Decimal("29.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=8, ram_gb=Decimal("8"), disk_gb=60, bandwidth_gb=1250, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-8", name="马来西亚（优质网络）-VM-8", price=Decimal("47.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=8, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=2000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-12", name="马来西亚（优质网络）-VM-12", price=Decimal("60.95"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=16, ram_gb=Decimal("16"), disk_gb=80, bandwidth_gb=2500, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="my-prem-16", name="马来西亚（优质网络）-VM-16", price=Decimal("95.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_DEPLOY_URL, in_stock=True, location="吉隆坡", line_tags=["CN2 GIA", "9929", "CMI"], cpu_cores=16, ram_gb=Decimal("32"), disk_gb=100, bandwidth_gb=4000, port_mbps=1000, from_preset=True, stock_verified=True),
]


class EvoxtCrawler(MerchantCrawler):
    slug = "evoxt"
    name = "Evoxt"
    default_interval_minutes = 5
    website = BASE
    crawl_method = "官方公开价格表 (/pricing/) 3大网络体系"
    aff_url_template = AFF_DEPLOY_URL

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        try:
            resp = client.get(PRICING_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if resp.status_code == 200:
                products = parse_evoxt_pricing_page(resp.text)
                if len(products) >= 10:
                    return products
        except Exception as e:
            logger.warning(f"[evoxt] fetch pricing page error: {e}")

        # 回退 1：d-vps 聚合源
        dvps = _fetch_dvps_fallback(client)
        if len(dvps) >= 8:
            print(f"[evoxt] live catalog: {len(dvps)} products from dvps source")
            return dvps

        # 回退 2：全量 33 款静态预置方案
        print(f"[evoxt] pricing page unavailable, fallback to {len(PRESET_EVOXT_PRODUCTS)} presets")
        return [RawProduct(**p.__dict__) for p in PRESET_EVOXT_PRODUCTS]
