"""VMiss 适配器。官网 https://www.vmiss.com，订购系统 https://app.vmiss.com（WHMCS lagom2 主题）。

app.vmiss.com 全站 Cloudflare 交互式人机验证（2026-08 实测数据中心 IP 无法直连），
策略与 DMIT 一致：实时优先 + 预置回退。
1. 实时：逐分组页抓取（lagom2 标准卡片结构，div.package#product{pid}，与 whmcs.py 解析器兼容）；
   检测到 Cloudflare 挑战页（403 / "Just a moment"）即视为该页失败。
2. 回退：预置目录（2026-05/06 官网页面存档校准，全部 15 个 VPS 分组 × 5 档），
   in_stock 一律 False（悲观默认，拿到真实抓取后由实时数据覆写）。

注意：KR Seoul TRI 分组 2026-04 存档与 KR Seoul INTL 分组 2026-05 存档存在 pid 冲突（62-66），
无法确认 TRI 当前 pid，故预置目录仅保留 INTL；TRI 由实时抓取补充。
"""

import json
import re
from decimal import Decimal

import httpx

from .base import MerchantCrawler, RawProduct
from .whmcs import GroupPage, parse_store_page

BASE = "https://app.vmiss.com"

# Cloudflare 挑战页特征
_RE_CF_CHALLENGE = re.compile(r"just a moment|performing security verification|challenge-platform", re.I)

# 分组页：slug → (中文机房, 线路标签)
# 线路依据分组官方命名：CN2 GIA / 9929 / CMIN2 / TRI(三网各自优化) / BGP(三网直连) / IIJ·INTL(国际)
CATEGORIES: list[tuple[str, str, list[str]]] = [
    ("us-los-angeles-cn2", "洛杉矶", ["CN2 GIA"]),
    ("us-los-angeles-9929", "洛杉矶", ["9929"]),
    ("us-los-angeles-cmin2", "洛杉矶", ["CMIN2"]),
    ("us-los-angeles-tri", "洛杉矶", ["CN2 GIA", "9929", "CMIN2"]),
    ("us-los-angeles-bgp", "洛杉矶", ["CN2 GIA", "9929", "CMIN2"]),  # H1 实为 TRI #DC2
    ("cn-hk-bgp-v2", "香港", ["普通BGP"]),
    ("cn-hk-bgp-v3", "香港", ["普通BGP"]),
    ("cn-hong-kong-bgp", "香港", ["普通BGP"]),
    ("cn-hong-kong-intl", "香港", ["国际线路"]),
    ("jp-tokyo-bgp", "东京", ["普通BGP"]),
    ("jp-tokyo-iij", "东京", ["国际线路"]),
    ("jp-tokyo-tri", "东京", ["CN2 GIA", "9929", "CMIN2"]),
    ("jp-osaka-iij", "大阪", ["国际线路"]),
    ("kr-seoul-intl", "首尔", ["国际线路"]),
    ("kr-seoul-tri", "首尔", ["CN2 GIA", "9929", "CMIN2"]),
    ("gb-london-9929", "伦敦", ["9929"]),
]


def _is_blocked(resp: httpx.Response) -> bool:
    """识别 Cloudflare 人机验证页（挑战页 HTTP 403，正文含挑战特征文案）。"""
    if resp.status_code == 403:
        return True
    return bool(_RE_CF_CHALLENGE.search(resp.text[:3000]))


def _fetch_live(client: httpx.Client) -> list[RawProduct]:
    results: list[RawProduct] = []
    blocked = 0
    for slug, location, line_tags in CATEGORIES:
        url = f"{BASE}/store/{slug}"
        try:
            resp = client.get(url)
            if _is_blocked(resp):
                blocked += 1
                continue
            resp.raise_for_status()
        except Exception as e:
            print(f"[vmiss] group {slug} fetch failed: {e}")
            continue
        results.extend(parse_store_page(resp.text, GroupPage(url, location, line_tags), BASE))
    if blocked:
        print(f"[vmiss] {blocked}/{len(CATEGORIES)} groups blocked by Cloudflare challenge")
    return results


# ── 预置目录（实时抓取被 Cloudflare 拦截时的回退，全部为缺货态，由实时数据覆写真实库存）──
PRESET_VMISS_PRODUCTS: list[RawProduct] = [
    RawProduct(external_id="7", name="US.LA.CN2.Basic", price=Decimal("6.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=7", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=300, port_mbps=200),
    RawProduct(external_id="8", name="US.LA.CN2.Core", price=Decimal("12.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=8", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=200),
    RawProduct(external_id="9", name="US.LA.CN2.Pro", price=Decimal("20.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=9", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=500),
    RawProduct(external_id="10", name="US.LA.CN2.Elite", price=Decimal("38.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=10", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1600, port_mbps=500),
    RawProduct(external_id="11", name="US.LA.CN2.Ultra", price=Decimal("75.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=11", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=2800, port_mbps=1000),
    RawProduct(external_id="57", name="US.LA.9929.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=57", in_stock=False, location="洛杉矶", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=500, port_mbps=200),
    RawProduct(external_id="58", name="US.LA.9929.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=58", in_stock=False, location="洛杉矶", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="59", name="US.LA.9929.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=59", in_stock=False, location="洛杉矶", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1500, port_mbps=300),
    RawProduct(external_id="60", name="US.LA.9929.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=60", in_stock=False, location="洛杉矶", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2500, port_mbps=500),
    RawProduct(external_id="61", name="US.LA.9929.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=61", in_stock=False, location="洛杉矶", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=4000, port_mbps=500),
    RawProduct(external_id="44", name="US.LA.CMIN2.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=44", in_stock=False, location="洛杉矶", line_tags=['CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=400, port_mbps=200),
    RawProduct(external_id="45", name="US.LA.CMIN2.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=45", in_stock=False, location="洛杉矶", line_tags=['CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=800, port_mbps=200),
    RawProduct(external_id="46", name="US.LA.CMIN2.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=46", in_stock=False, location="洛杉矶", line_tags=['CMIN2'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1200, port_mbps=300),
    RawProduct(external_id="47", name="US.LA.CMIN2.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=47", in_stock=False, location="洛杉矶", line_tags=['CMIN2'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=500),
    RawProduct(external_id="48", name="US.LA.CMIN2.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=48", in_stock=False, location="洛杉矶", line_tags=['CMIN2'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3200, port_mbps=500),
    RawProduct(external_id="32", name="US.LA.TRI.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=32", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=500, port_mbps=200),
    RawProduct(external_id="33", name="US.LA.TRI.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=33", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="34", name="US.LA.TRI.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=34", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("3.0"), disk_gb=20, bandwidth_gb=1500, port_mbps=300),
    RawProduct(external_id="35", name="US.LA.TRI.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=35", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2500, port_mbps=300),
    RawProduct(external_id="36", name="US.LA.TRI.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=36", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=4000, port_mbps=500),
    RawProduct(external_id="1", name="US.LA.TRI.DC2.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=1", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=400, port_mbps=200),
    RawProduct(external_id="3", name="US.LA.TRI.DC2.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=3", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=800, port_mbps=200),
    RawProduct(external_id="4", name="US.LA.TRI.DC2.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=4", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1200, port_mbps=500),
    RawProduct(external_id="5", name="US.LA.TRI.DC2.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=5", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=500),
    RawProduct(external_id="6", name="US.LA.TRI.DC2.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=6", in_stock=False, location="洛杉矶", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3200, port_mbps=1000),
    RawProduct(external_id="83", name="CN.HK.BGP.DC2.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=83", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=400, port_mbps=100),
    RawProduct(external_id="84", name="CN.HK.BGP.DC2.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=84", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=800, port_mbps=100),
    RawProduct(external_id="85", name="CN.HK.BGP.DC2.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=85", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1200, port_mbps=200),
    RawProduct(external_id="86", name="CN.HK.BGP.DC2.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=86", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=200),
    RawProduct(external_id="87", name="CN.HK.BGP.DC2.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=87", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3600, port_mbps=300),
    RawProduct(external_id="90", name="CN.HK.BGP.DC3.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=90", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=300, port_mbps=100),
    RawProduct(external_id="91", name="CN.HK.BGP.DC3.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=91", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=100),
    RawProduct(external_id="92", name="CN.HK.BGP.DC3.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=92", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=100),
    RawProduct(external_id="93", name="CN.HK.BGP.DC3.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=93", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1600, port_mbps=100),
    RawProduct(external_id="94", name="CN.HK.BGP.DC3.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=94", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3000, port_mbps=100),
    RawProduct(external_id="50", name="CN.HK.BGP.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=50", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=300, port_mbps=100),
    RawProduct(external_id="53", name="CN.HK.BGP.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=53", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=100),
    RawProduct(external_id="54", name="CN.HK.BGP.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=54", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=150),
    RawProduct(external_id="55", name="CN.HK.BGP.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=55", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1600, port_mbps=150),
    RawProduct(external_id="56", name="CN.HK.BGP.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=56", in_stock=False, location="香港", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3000, port_mbps=200),
    RawProduct(external_id="38", name="CN.HK.INTL.Basic", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=38", in_stock=False, location="香港", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=1000, port_mbps=500),
    RawProduct(external_id="39", name="CN.HK.INTL.Core", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=39", in_stock=False, location="香港", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=2000, port_mbps=500),
    RawProduct(external_id="40", name="CN.HK.INTL.Pro", price=Decimal("54.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=40", in_stock=False, location="香港", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=3000, port_mbps=800),
    RawProduct(external_id="42", name="CN.HK.INTL.Elite", price=Decimal("72.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=42", in_stock=False, location="香港", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="43", name="CN.HK.INTL.Ultra", price=Decimal("18.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=43", in_stock=False, location="香港", line_tags=['国际线路'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=5000, port_mbps=1000),
    RawProduct(external_id="72", name="JP.TKY.BGP.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=72", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=400, port_mbps=500),
    RawProduct(external_id="73", name="JP.TKY.BGP.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=73", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=800, port_mbps=500),
    RawProduct(external_id="74", name="JP.TKY.BGP.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=74", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1200, port_mbps=750),
    RawProduct(external_id="75", name="JP.TKY.BGP.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=75", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=750),
    RawProduct(external_id="76", name="JP.TKY.BGP.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=76", in_stock=False, location="东京", line_tags=['普通BGP'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3200, port_mbps=1000),
    RawProduct(external_id="67", name="JP.TKY.IIJ.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=67", in_stock=False, location="东京", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=500, port_mbps=500),
    RawProduct(external_id="68", name="JP.TKY.IIJ.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=68", in_stock=False, location="东京", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=800, port_mbps=500),
    RawProduct(external_id="69", name="JP.TKY.IIJ.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=69", in_stock=False, location="东京", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1500, port_mbps=750),
    RawProduct(external_id="70", name="JP.TKY.IIJ.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=70", in_stock=False, location="东京", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2500, port_mbps=750),
    RawProduct(external_id="71", name="JP.TKY.IIJ.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=71", in_stock=False, location="东京", line_tags=['国际线路'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="101", name="JP.TKY.TRI.Basic", price=Decimal("12.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=101", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=400, port_mbps=100),
    RawProduct(external_id="102", name="JP.TKY.TRI.Core", price=Decimal("24.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=102", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=15, bandwidth_gb=800, port_mbps=100),
    RawProduct(external_id="103", name="JP.TKY.TRI.Pro", price=Decimal("38.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=103", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=1, ram_gb=Decimal("3.0"), disk_gb=20, bandwidth_gb=1200, port_mbps=200),
    RawProduct(external_id="104", name="JP.TKY.TRI.Elite", price=Decimal("75.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=104", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=200),
    RawProduct(external_id="105", name="JP.TKY.TRI.Ultra", price=Decimal("150.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=105", in_stock=False, location="东京", line_tags=['CN2 GIA', '9929', 'CMIN2'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=3200, port_mbps=300),
    RawProduct(external_id="25", name="JP.OSA.IIJ.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=25", in_stock=False, location="大阪", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=500, port_mbps=500),
    RawProduct(external_id="26", name="JP.OSA.IIJ.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=26", in_stock=False, location="大阪", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=500),
    RawProduct(external_id="27", name="JP.OSA.IIJ.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=27", in_stock=False, location="大阪", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1500, port_mbps=750),
    RawProduct(external_id="28", name="JP.OSA.IIJ.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=28", in_stock=False, location="大阪", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2500, port_mbps=750),
    RawProduct(external_id="29", name="JP.OSA.IIJ.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=29", in_stock=False, location="大阪", line_tags=['国际线路'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=4000, port_mbps=1000),
    RawProduct(external_id="62", name="KR.SEL.INTL.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=62", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=300, port_mbps=50),
    RawProduct(external_id="63", name="KR.SEL.INTL.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=63", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=600, port_mbps=50),
    RawProduct(external_id="64", name="KR.SEL.INTL.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=64", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=60),
    RawProduct(external_id="65", name="KR.SEL.INTL.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=65", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=1600, port_mbps=60),
    RawProduct(external_id="66", name="KR.SEL.INTL.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=66", in_stock=False, location="首尔", line_tags=['国际线路'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=2600, port_mbps=75),
    RawProduct(external_id="78", name="GB.LON.9929.Basic", price=Decimal("5.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=78", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=500, port_mbps=200),
    RawProduct(external_id="79", name="GB.LON.9929.Core", price=Decimal("10.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=79", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=200),
    RawProduct(external_id="80", name="GB.LON.9929.Pro", price=Decimal("16.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=80", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1500, port_mbps=300),
    RawProduct(external_id="81", name="GB.LON.9929.Elite", price=Decimal("30.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=81", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2500, port_mbps=300),
    RawProduct(external_id="82", name="GB.LON.9929.Ultra", price=Decimal("60.00"), currency="CAD", billing_cycle="monthly", purchase_url="https://app.vmiss.com/cart.php?a=add&pid=82", in_stock=False, location="伦敦", line_tags=['9929'], cpu_cores=4, ram_gb=Decimal("8.0"), disk_gb=80, bandwidth_gb=4000, port_mbps=400),
]


def _fetch_stockvps(client: httpx.Client) -> dict[str, bool]:
    """从 stockvps.org 第三方实时监控源提取 VMiss 全量套餐库存状态。"""
    try:
        resp = client.get("https://stockvps.org", timeout=15.0)
        resp.raise_for_status()
        start_marker = r"\"plans\":["
        idx = resp.text.find(start_marker)
        if idx == -1:
            return {}
        end_marker = r"],\"providers\":"
        idx_end = resp.text.find(end_marker, idx)
        if idx_end == -1:
            return {}
        raw = resp.text[idx + len(start_marker) - 1 : idx_end + 1]
        unescaped = raw.replace(r"\"", "\"").replace(r"\\", "\\")
        plans = json.loads(unescaped)
        stock_map: dict[str, bool] = {}
        for p in plans:
            if p.get("provider") == "VMISS":
                link = p.get("link") or ""
                pid = link.split("/")[-1]
                if pid.isdigit():
                    stock_val = p.get("stock")
                    # stock != 0 为有货（-1 表示不限量/有货，>0 表示剩余件数）
                    stock_map[pid] = (stock_val != 0)
        return stock_map
    except Exception as e:
        print(f"[vmiss] stockvps monitor source warning: {e}")
        return {}


class VmissCrawler(MerchantCrawler):
    slug = "vmiss"
    name = "VMiss"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://www.vmiss.com"
    # 返利：WHMCS 标准 aff.php，带 pid 直达套餐（同 DMIT 模式；上线前请实测确认跳转）
    aff_url_template = "https://app.vmiss.com/aff.php?aff=6324&pid={pid}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        # 源 1：尝试官网直连抓取
        live = _fetch_live(client)
        if len(live) >= 10:
            print(f"[vmiss] live catalog: {len(live)} products from store pages")
            return live

        # 源 2：从第三方监控源（stockvps.org）合并实时库存状态
        stock_map = _fetch_stockvps(client)
        if stock_map:
            print(f"[vmiss] store pages challenge fallback: overlay {len(stock_map)} live stocks from third-party monitor")
            return [
                RawProduct(
                    external_id=p.external_id,
                    name=p.name,
                    price=p.price,
                    currency=p.currency,
                    billing_cycle=p.billing_cycle,
                    price_options=list(p.price_options or []),
                    purchase_url=p.purchase_url,
                    in_stock=stock_map.get(p.external_id, False),
                    location=p.location,
                    line_tags=list(p.line_tags),
                    cpu_cores=p.cpu_cores,
                    ram_gb=p.ram_gb,
                    disk_gb=p.disk_gb,
                    bandwidth_gb=p.bandwidth_gb,
                    port_mbps=p.port_mbps,
                    from_preset=True,
                )
                for p in PRESET_VMISS_PRODUCTS
            ]

        # 源 3：最终兜底（静态预置目录，全部悲观缺货，不参与消失标记）
        print(f"[vmiss] all live sources unavailable, fallback to {len(PRESET_VMISS_PRODUCTS)} static presets (OOS)")
        return [
            RawProduct(
                external_id=p.external_id,
                name=p.name,
                price=p.price,
                currency=p.currency,
                billing_cycle=p.billing_cycle,
                price_options=list(p.price_options or []),
                purchase_url=p.purchase_url,
                in_stock=False,
                location=p.location,
                line_tags=list(p.line_tags),
                cpu_cores=p.cpu_cores,
                ram_gb=p.ram_gb,
                disk_gb=p.disk_gb,
                bandwidth_gb=p.bandwidth_gb,
                port_mbps=p.port_mbps,
                from_preset=True,
            )
            for p in PRESET_VMISS_PRODUCTS
        ]
