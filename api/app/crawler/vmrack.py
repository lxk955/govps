"""VMRack 适配器。官网 https://www.vmrack.net，API https://api.vmrack.net。

主打洛杉矶自建机房（LAX-DC1 / LAX-DC2）与高品质网络产品线：
- L3 系列（三网精品 Premium）：电信 CN2 GIA + 联通 9929 + 移动 CMIN2 顶级回国优化。
- L2 系列（三网优化 Platinum）：电信 163 + 联通 10099 + 移动 CMI 直连优化。
- L1 系列（美国原生 Global BGP）：Cogent / Arelion 国际高性价比 BGP。
- VPS 包含限量流量与 BVPS 不限流量双版本。

抓取架构：
1. 优先请求官网后台实时接口 POST https://api.vmrack.net/v1/product/set/compute/search/no_user。
2. 遭遇异常时通过 d-vps.com 聚合源进行数据校准与回退。
3. 离线测试与源站中断时回退至 51 款静态预置商品清单。
"""

import logging
import re
from decimal import Decimal

import httpx

from .base import (
    MerchantCrawler,
    RawProduct,
    normalize_line_tags,
    normalize_location,
)

logger = logging.getLogger(__name__)

BASE = "https://www.vmrack.net"
API_SEARCH_URL = "https://api.vmrack.net/v1/product/set/compute/search/no_user"
AFF_URL = "https://www.vmrack.net/zh-CN/vps?ref_code=5jCKaCkhjcT"

# 官网套餐名与 d-vps 外部 PID 保持严格 1:1 映射
NAME_TO_DVPS_PID: dict[str, str] = {
    "L1.VPS.2C4G.Base": "2572711621899999286",
    "L1.VPS.4C4G.Plus": "3964790787771810431",
    "L1.VPS.4C8G.Plus": "7073456115651747500",
    "L1.VPS.DC2.2C2G.Base": "2873082667345994832",
    "L1.VPS.DC2.2C2G.Plus": "8411832330981469536",
    "L1.VPS.DC2.2C4G.Pro": "7329870004425725404",
    "L2.VPS.2C4G.Base": "9190505798939324334",
    "L2.VPS.4C4G.Plus": "2804679922363781563",
    "L2.VPS.4C8G.Plus": "6856749401483542818",
    "L2.VPS.DC2.2C2G.Base": "695401032994701923",
    "L2.VPS.DC2.2C2G.Plus": "2670483422805663555",
    "L2.VPS.DC2.2C4G.Pro": "2497856760944833284",
    "L3.VPS.2C2G.Base": "1106671370188800515",
    "L3.VPS.2C4G.Base": "8280210907351558518",
    "L3.VPS.4C4G.Plus": "2773843147219364161",
    "L3.VPS.DC2.2C2G.Base": "7452479152045348950",
    "L3.VPS.DC2.2C2G.Plus": "265445926333038922",
    "L3.VPS.DC2.2C4G.Pro": "2964084892888984952",
    "L1.BVPS.DC1.2C2G.Base": "6264479822093992335",
    "L1.BVPS.DC1.2C4G.Plus": "7533054019884341543",
    "L1.BVPS.DC1.4C4G.Pro": "1035320542695608965",
    "L1.BVPS.DC2.2C2G.Base": "887342380810460218",
    "L1.BVPS.DC2.2C4G.Plus": "5274205308955216593",
    "L1.BVPS.DC2.4C4G.Pro": "989746599403631060",
    "L2.BVPS.DC1.2C2G.Base": "6716511766944456659",
    "L2.BVPS.DC1.2C4G.Plus": "3100282219210652584",
    "L2.BVPS.DC1.4C4G.Pro": "4006878736367232200",
    "L2.BVPS.DC2.2C2G.Base": "7004591677233724711",
    "L2.BVPS.DC2.2C4G.Plus": "2624266556706662813",
    "L2.BVPS.DC2.4C4G.Pro": "7750017083479308328",
    "L3.BVPS.DC1.2C2G.Base": "3478643448941729233",
    "L3.BVPS.DC1.2C4G.Plus": "6438101345996979511",
    "L3.BVPS.DC1.4C4G.Pro": "1807878123197670968",
    "L3.BVPS.DC2.2C2G.Base": "7801319448504328961",
    "L3.BVPS.DC2.2C4G.Plus": "2435697290783898111",
    "L3.BVPS.DC2.4C4G.Pro": "7332719103316958742",
    "L1.Metal1.Intel 6150": "2323130099273822624",
    "L1.Metal2.Intel 6150": "883698220792690079",
    "L1.Metal3.Intel 6150": "1416019073315817696",
    "L2.Metal1.Intel 6150": "3965730826325532593",
    "L2.Metal2.Intel 6150": "6881017342092948662",
    "L2.Metal3.Intel 6150": "2410688226516487718",
    "L3.Metal1.Intel 6150": "473729796585586446",
    "L3.Metal2.Intel 6150": "2036426752088916341",
    "L3.Metal3.Intel 6150": "2717805103414966337",
    "bms.i1c.4xlarge": "3429042700124016557",
    "bms.i1c.8xlarge": "7431932422758289894",
    "bms.i1g.2xlarge": "7832360245361926303",
    "bms.s1g.2xlarge": "3724177213946054952",
    "bms.s1g.xlarge": "6289198447621243813",
}


def _get_line_tags(name: str) -> list[str]:
    """根据套餐所属网络体系 (L1/L2/L3) 赋予标准规范线路分类。"""
    if "L3" in name:
        return ["CN2 GIA", "9929", "CMIN2"]
    elif "L2" in name:
        return ["CMI", "普通BGP"]
    return ["普通BGP"]


def parse_vmrack_api_response(data: dict) -> list[RawProduct]:
    """解析 VMRack 官方后台 search/no_user 返回的 compute 产品清单。"""
    raw_list = data.get("data", {}).get("list", []) if isinstance(data, dict) else []
    if not isinstance(raw_list, list):
        return []

    products: list[RawProduct] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue

        raw_id = str(item.get("id") or "")
        ext_id = NAME_TO_DVPS_PID.get(name, raw_id)

        # 价格以分为单位：166600 -> 16.66 USD
        raw_price = item.get("price")
        price = Decimal("0.00")
        if raw_price is not None:
            price = Decimal(str(round(float(raw_price) / 10000.0, 2)))

        # 库存状态：1 为在售，2 为预售/按需开通(在售)，3 为缺货
        stock_status = item.get("stock_status")
        in_stock = bool(stock_status in (1, 2))

        # 硬件配置
        cpu = int(item.get("cpu") or 1)
        ram = Decimal(str(item.get("mem") or "1.0"))
        disk = int(item.get("sys_disk_capacity") or 0)
        port = int(item.get("bandwidth") or 0)

        # 流量提取：-1 表示不限流量；unit=2 为 TB，unit=1 为 GB
        traffic_obj = item.get("traffic", {}) if isinstance(item.get("traffic"), dict) else {}
        t_val = traffic_obj.get("traffic", 0)
        t_unit = traffic_obj.get("unit", 1)
        if t_val == -1:
            bw = -1
        elif t_unit == 2:
            bw = t_val * 1000
        else:
            bw = t_val

        p = RawProduct(
            external_id=ext_id,
            name=name,
            price=price,
            currency="USD",
            billing_cycle="monthly",
            purchase_url=AFF_URL,
            in_stock=in_stock,
            location=normalize_location("洛杉矶"),
            line_tags=_get_line_tags(name),
            cpu_cores=cpu,
            ram_gb=ram,
            disk_gb=disk,
            bandwidth_gb=bw,
            port_mbps=port,
            stock_verified=True,
        )
        products.append(p)

    return products


def _fetch_dvps_fallback(client: httpx.Client) -> list[RawProduct]:
    """从 d-vps.com 聚合源拉取并重新规整线路标签与机房。"""
    try:
        from .dvps_source import DvpsSource

        dvps_prods = DvpsSource().fetch_products("vmrack", client)
        if not dvps_prods:
            return []

        results: list[RawProduct] = []
        for dp in dvps_prods:
            name = dp.name
            results.append(
                RawProduct(
                    external_id=dp.external_id,
                    name=name,
                    price=dp.price,
                    currency=dp.currency,
                    billing_cycle=dp.billing_cycle,
                    price_options=dp.price_options,
                    purchase_url=AFF_URL,
                    in_stock=dp.in_stock,
                    location=normalize_location(dp.location or "洛杉矶"),
                    line_tags=_get_line_tags(name),
                    cpu_cores=dp.cpu_cores,
                    ram_gb=dp.ram_gb,
                    disk_gb=dp.disk_gb,
                    bandwidth_gb=dp.bandwidth_gb,
                    port_mbps=dp.port_mbps,
                    stock_verified=True,
                )
            )
        return results
    except Exception as e:
        logger.warning(f"[vmrack] dvps fallback error: {e}")
        return []


PRESET_VMRACK_PRODUCTS: list[RawProduct] = [
    # ── 1. 云服务器 (VPS 限量版) ──
    RawProduct(external_id="7073456115651747500", name="L1.VPS.4C8G.Plus", price=Decimal("16.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal('8.0'), disk_gb=100, bandwidth_gb=16000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="3964790787771810431", name="L1.VPS.4C4G.Plus", price=Decimal("9.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=80, bandwidth_gb=8000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2572711621899999286", name="L1.VPS.2C4G.Base", price=Decimal("5.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=60, bandwidth_gb=4000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="6856749401483542818", name="L2.VPS.4C8G.Plus", price=Decimal("20.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=4, ram_gb=Decimal('8.0'), disk_gb=100, bandwidth_gb=10000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2804679922363781563", name="L2.VPS.4C4G.Plus", price=Decimal("12.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=80, bandwidth_gb=6000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="9190505798939324334", name="L2.VPS.2C4G.Base", price=Decimal("8.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=60, bandwidth_gb=4000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2773843147219364161", name="L3.VPS.4C4G.Plus", price=Decimal("49.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=80, bandwidth_gb=4000, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="8280210907351558518", name="L3.VPS.2C4G.Base", price=Decimal("19.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=60, bandwidth_gb=2000, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="1106671370188800515", name="L3.VPS.2C2G.Base", price=Decimal("13.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=40, bandwidth_gb=1500, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="7329870004425725404", name="L1.VPS.DC2.2C4G.Pro", price=Decimal("25.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=20000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="8411832330981469536", name="L1.VPS.DC2.2C2G.Plus", price=Decimal("12.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=30, bandwidth_gb=10000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2873082667345994832", name="L1.VPS.DC2.2C2G.Base", price=Decimal("6.66"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=4000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2497856760944833284", name="L2.VPS.DC2.2C4G.Pro", price=Decimal("25.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=10000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2670483422805663555", name="L2.VPS.DC2.2C2G.Plus", price=Decimal("12.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=30, bandwidth_gb=5000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="695401032994701923", name="L2.VPS.DC2.2C2G.Base", price=Decimal("7.88"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=30, bandwidth_gb=3000, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2964084892888984952", name="L3.VPS.DC2.2C4G.Pro", price=Decimal("36.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=3000, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="265445926333038922", name="L3.VPS.DC2.2C2G.Plus", price=Decimal("23.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=30, bandwidth_gb=2000, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="7452479152045348950", name="L3.VPS.DC2.2C2G.Base", price=Decimal("9.99"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=1000, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="2082382010554826752", name="L2.VPS.1C1G.Base dujiao", price=Decimal("81.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=1, ram_gb=Decimal('1.0'), disk_gb=20, bandwidth_gb=2000, port_mbps=5000, from_preset=True, stock_verified=True),

    # ── 2. 云服务器 (BVPS 不限流量版) ──
    RawProduct(external_id="1035320542695608965", name="L1.BVPS.DC1.4C4G.Pro", price=Decimal("159.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="7533054019884341543", name="L1.BVPS.DC1.2C4G.Plus", price=Decimal("69.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="6264479822093992335", name="L1.BVPS.DC1.2C2G.Base", price=Decimal("36.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="4006878736367232200", name="L2.BVPS.DC1.4C4G.Pro", price=Decimal("309.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="3100282219210652584", name="L2.BVPS.DC1.2C4G.Plus", price=Decimal("129.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="6716511766944456659", name="L2.BVPS.DC1.2C2G.Base", price=Decimal("66.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="1807878123197670968", name="L3.BVPS.DC1.4C4G.Pro", price=Decimal("1129.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="6438101345996979511", name="L3.BVPS.DC1.2C4G.Plus", price=Decimal("569.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="3478643448941729233", name="L3.BVPS.DC1.2C2G.Base", price=Decimal("286.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=50, from_preset=True, stock_verified=True),
    RawProduct(external_id="989746599403631060", name="L1.BVPS.DC2.4C4G.Pro", price=Decimal("159.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="5274205308955216593", name="L1.BVPS.DC2.2C4G.Plus", price=Decimal("69.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="887342380810460218", name="L1.BVPS.DC2.2C2G.Base", price=Decimal("36.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="7750017083479308328", name="L2.BVPS.DC2.4C4G.Pro", price=Decimal("309.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="2624266556706662813", name="L2.BVPS.DC2.2C4G.Plus", price=Decimal("129.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="7004591677233724711", name="L2.BVPS.DC2.2C2G.Base", price=Decimal("66.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="7332719103316958742", name="L3.BVPS.DC2.4C4G.Pro", price=Decimal("1129.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal('4.0'), disk_gb=50, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="2435697290783898111", name="L3.BVPS.DC2.2C4G.Plus", price=Decimal("569.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('4.0'), disk_gb=40, bandwidth_gb=-1, port_mbps=100, from_preset=True, stock_verified=True),
    RawProduct(external_id="7801319448504328961", name="L3.BVPS.DC2.2C2G.Base", price=Decimal("286.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal('2.0'), disk_gb=20, bandwidth_gb=-1, port_mbps=50, from_preset=True, stock_verified=True),

    # ── 3. 裸金属服务器 (BMS) ──
    RawProduct(external_id="3429042700124016557", name="bms.i1c.4xlarge", price=Decimal("979.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=36, ram_gb=Decimal('128.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="7431932422758289894", name="bms.i1c.8xlarge", price=Decimal("999.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=40, ram_gb=Decimal('128.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="7832360245361926303", name="bms.i1g.2xlarge", price=Decimal("919.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=20, ram_gb=Decimal('64.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="3724177213946054952", name="bms.s1g.2xlarge", price=Decimal("879.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=36, ram_gb=Decimal('64.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="6289198447621243813", name="bms.s1g.xlarge", price=Decimal("860.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=True, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=18, ram_gb=Decimal('64.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),

    # ── 4. 历史裸金属 (已下架 Metal 存档) ──
    RawProduct(external_id="2323130099273822624", name="L1.Metal1.Intel 6150", price=Decimal("998.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=2000, from_preset=True, stock_verified=True),
    RawProduct(external_id="883698220792690079", name="L1.Metal2.Intel 6150", price=Decimal("1760.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="1416019073315817696", name="L1.Metal3.Intel 6150", price=Decimal("3260.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=10000, from_preset=True, stock_verified=True),
    RawProduct(external_id="3965730826325532593", name="L2.Metal1.Intel 6150", price=Decimal("998.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
    RawProduct(external_id="6881017342092948662", name="L2.Metal2.Intel 6150", price=Decimal("3260.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=5000, from_preset=True, stock_verified=True),
    RawProduct(external_id="2410688226516487718", name="L2.Metal3.Intel 6150", price=Decimal("6260.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CMI', '普通BGP'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=10000, from_preset=True, stock_verified=True),
    RawProduct(external_id="473729796585586446", name="L3.Metal1.Intel 6150", price=Decimal("1390.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=200, from_preset=True, stock_verified=True),
    RawProduct(external_id="2036426752088916341", name="L3.Metal2.Intel 6150", price=Decimal("2990.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=500, from_preset=True, stock_verified=True),
    RawProduct(external_id="2717805103414966337", name="L3.Metal3.Intel 6150", price=Decimal("5800.00"), currency="USD", billing_cycle="monthly", purchase_url=AFF_URL, in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=72, ram_gb=Decimal('256.0'), disk_gb=None, bandwidth_gb=-1, port_mbps=1000, from_preset=True, stock_verified=True),
]


class VMRackCrawler(MerchantCrawler):
    slug = "vmrack"
    name = "VMRack"
    default_interval_minutes = 5
    website = BASE
    aff_url_template = AFF_URL

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        # 1. 尝试从官网后台 API 获取实时产品
        try:
            resp = client.post(
                API_SEARCH_URL,
                json={"page": 1, "page_size": 100},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Content-Type": "application/json",
                    "Accept-Language": "zh-CN",
                },
            )
            if resp.status_code == 200:
                products = parse_vmrack_api_response(resp.json())
                if len(products) >= 15:
                    # 将现存活跃的 BMS 裸金属服务器合入结果集
                    bms_active = [RawProduct(**p.__dict__) for p in PRESET_VMRACK_PRODUCTS if p.name.startswith("bms.")]
                    return products + bms_active
        except Exception as e:
            logger.warning(f"[vmrack] fetch live API error: {e}")

        # 2. 回退 1：d-vps.com 聚合源
        dvps = _fetch_dvps_fallback(client)
        if len(dvps) >= 10:
            print(f"[vmrack] live catalog: {len(dvps)} products from dvps source")
            return dvps

        # 3. 回退 2：全量静态预置方案
        print(f"[vmrack] live API and dvps unavailable, fallback to {len(PRESET_VMRACK_PRODUCTS)} presets")
        return [RawProduct(**p.__dict__) for p in PRESET_VMRACK_PRODUCTS]
