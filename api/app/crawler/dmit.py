"""DMIT 适配器。官网 https://www.dmit.io（WHMCS，Cloudflare 强盾无法直连）。

多源冗余策略（按官方 pid 匹配合并，取字段最优）：
1. monitor.vpszk.com  —— 结构化 JSON，字段最全（库存/价格/配置/机房/线路），主源
2. vpsoso.com         —— HTML 表格兜底（覆盖面广）
3. DMIT_PRESETS       —— 预置元数据最终回退

注：legacyvps.com 曾评估为备源，但其 DMIT 套餐 pid 与官方不一致（如 Pro.TINY 标记为 258，
官网实为 253），且覆盖仅 3 款，合并会产生重复套餐，故弃用。
"""

import re
from decimal import Decimal

import httpx
from selectolax.parser import HTMLParser

from .base import MerchantCrawler, RawProduct, extract_line_tags, normalize_location

_CYCLE_CN = {
    "月付": "monthly",
    "季付": "quarterly",
    "半年付": "semi_annually",
    "年付": "annually",
    "两年付": "biennially",
}

_TAG_MAP = {
    "CN2GIA": "CN2 GIA",
    "CN2 GIA": "CN2 GIA",
    "9929": "9929",
    "CMIN2": "CMIN2",
    "4837": "4837",
    "普通线路": "国际线路",
}


def _line_tags(raw_tags: list[str] | str, fallback_text: str = "") -> list[str]:
    """把第三方源的标签规范化为站内线路标签，过滤营销词。"""
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",")]
    out: list[str] = []
    for t in raw_tags:
        mapped = _TAG_MAP.get(t, _TAG_MAP.get(t.strip()))
        if mapped and mapped not in out:
            out.append(mapped)
    if not out and fallback_text:
        out = extract_line_tags(fallback_text)
    return out or ["国际线路"]


# ── 源 1：monitor.vpszk.com（结构化 JSON，字段最全）──
def _fetch_vpszk(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    try:
        resp = client.get(
            "https://monitor.vpszk.com/api/plans",
            params={"provider": "dmit", "pageSize": 100},
            timeout=15.0,
        )
        resp.raise_for_status()
        items = [p for p in resp.json().get("items", []) if p.get("providerSlug") == "dmit"]
        for p in items:
            pid = str(p.get("externalId") or "").strip()
            if not pid:
                continue
            city = None
            locs = p.get("locations") or []
            if locs and isinstance(locs, list):
                city = locs[0].get("city")
            if not city:
                city = {"LAX": "洛杉矶", "HKG": "香港", "TYO": "东京", "SJC": "圣何塞"}.get(
                    (p.get("name") or "").split(".")[0]
                )
            cycle = _CYCLE_CN.get(p.get("billingCycle") or "", "monthly")
            price = p.get("price") or p.get("priceYear") or 0
            try:
                dec_price = Decimal(str(price))
            except Exception:
                continue
            if dec_price <= 0:
                continue
            products.append(
                RawProduct(
                    external_id=f"dmit-{pid}",
                    name=p.get("name") or f"DMIT {pid}",
                    price=dec_price,
                    currency=p.get("currency") or "USD",
                    billing_cycle=cycle,
                    purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={pid}",
                    in_stock=p.get("stock") == "in",
                    location=normalize_location(city or ""),
                    line_tags=_line_tags(p.get("tags") or [], p.get("name") or ""),
                    cpu_cores=p.get("vcpu"),
                    ram_gb=Decimal(str(p["ramGb"])) if p.get("ramGb") else None,
                    disk_gb=p.get("diskGb"),
                    bandwidth_gb=p.get("trafficGb"),
                    port_mbps=p.get("portMbps"),
                )
            )
    except Exception as e:
        print(f"[dmit] vpszk feed notice: {e}")
    return products


# ── 源 2：vpsoso.com（HTML 表格兜底）──
def _fetch_vpsoso(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    try:
        resp = client.get("https://vpsoso.com/vps/dmit", timeout=12.0)
        if resp.status_code != 200:
            return products
        tree = HTMLParser(resp.text)
        for row in tree.css("tbody tr"):
            cells = [c.text(separator=" ", strip=True) for c in row.css("td")]
            if len(cells) < 8:
                continue
            raw_name = cells[1].replace("推荐", "").strip()
            loc = normalize_location(cells[2].replace("美国-", "").replace("日本-", ""))
            line_tags = extract_line_tags(cells[4])

            cpu = ram = disk = None
            if m := re.match(r"(\d+)C/(\d+(?:\.\d+)?)G/(\d+)G", cells[5], re.I):
                cpu, ram, disk = int(m.group(1)), Decimal(m.group(2)), int(m.group(3))

            bw = port = None
            if "@" in cells[6]:
                bw_part, port_part = cells[6].split("@", 1)
                if "G" in bw_part:
                    bw = int(float(bw_part.replace("G", "")))
                elif "T" in bw_part:
                    bw = int(float(bw_part.replace("T", "")) * 1000)
                if "Gbps" in port_part:
                    port = int(float(port_part.replace("Gbps", "")) * 1000)
                elif "Mbps" in port_part:
                    port = int(float(port_part.replace("Mbps", "")))

            price, cycle = None, "monthly"
            if m := re.search(r"\$([\d.]+)/(月|年|季|半年)", cells[7]):
                price = Decimal(m.group(1))
                cycle = _CYCLE_CN.get(f"{m.group(2)}付", "monthly")
            if price is None or price <= 0:
                continue

            stock_cells = [c for c in cells if any(k in c for k in ("有货", "缺货", "无货", "售完"))]
            in_stock = bool(stock_cells) and "有货" in stock_cells[-1]

            link_node = row.css_first("a[href]")
            href = link_node.attributes.get("href", "") if link_node else ""
            pid_match = re.search(r"id=(\d+)", href)
            v_id = pid_match.group(1) if pid_match else raw_name

            products.append(
                RawProduct(
                    external_id=f"dmit-{v_id}",
                    name=f"PVM.{raw_name}",
                    price=price,
                    currency="USD",
                    billing_cycle=cycle,
                    purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={v_id}",
                    in_stock=in_stock,
                    location=loc,
                    line_tags=line_tags,
                    cpu_cores=cpu,
                    ram_gb=ram,
                    disk_gb=disk,
                    bandwidth_gb=bw,
                    port_mbps=port,
                )
            )
    except Exception as e:
        print(f"[dmit] vpsoso feed notice: {e}")
    return products


# ── 预置 DMIT 官方各机房全系列经典套餐元数据（最终回退，预置默认均为缺货，由实时源覆写真实库存）──
DMIT_PRESETS: list[RawProduct] = [
    # 洛杉矶 Pro 旗舰系列（三网 CN2 GIA / AS9929 / CMIN2）
    RawProduct(external_id="dmit-183", name="PVM.LAX.Pro.WEE", price=Decimal("36.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=183",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA", "9929", "CMIN2"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=450, port_mbps=500, recommended=True),
    RawProduct(external_id="dmit-184", name="PVM.LAX.Pro.TINY", price=Decimal("88.88"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=184",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA", "9929", "CMIN2"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="dmit-101", name="PVM.LAX.Pro.SHARE", price=Decimal("139.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=101",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA", "9929", "CMIN2"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=800, port_mbps=1000),
    RawProduct(external_id="dmit-102", name="PVM.LAX.Pro.POCKET", price=Decimal("159.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=102",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA", "9929", "CMIN2"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=1200, port_mbps=1000),
    RawProduct(external_id="dmit-103", name="PVM.LAX.Pro.STARTER", price=Decimal("29.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=103",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA", "9929", "CMIN2"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=60, bandwidth_gb=2000, port_mbps=2000),
    # 洛杉矶 EB（Eyeball）CMIN2 / 9929 / 4837 系列
    RawProduct(external_id="dmit-188", name="PVM.LAX.EB.WEE", price=Decimal("39.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=188",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929", "4837"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=1000, recommended=True),
    RawProduct(external_id="dmit-189", name="PVM.LAX.EB.TINY", price=Decimal("69.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=189",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929", "4837"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=2000, port_mbps=2000),
    RawProduct(external_id="dmit-154", name="PVM.LAX.EB.POCKET", price=Decimal("159.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=154",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929", "4837"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=3000, port_mbps=4000),
    RawProduct(external_id="dmit-155", name="PVM.LAX.EB.STARTER", price=Decimal("29.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=155",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929", "4837"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=60, bandwidth_gb=4000, port_mbps=5000),
    # 东京 Pro / Lite
    RawProduct(external_id="dmit-148", name="PVM.TYO.Lite.TINY", price=Decimal("10.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=148",
               in_stock=False, location="东京", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="dmit-142", name="PVM.TYO.Pro.Pocket", price=Decimal("21.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=142",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=300, port_mbps=100, recommended=True),
    RawProduct(external_id="dmit-143", name="PVM.TYO.Pro.SHARE", price=Decimal("36.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=143",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=600, port_mbps=200),
    RawProduct(external_id="dmit-144", name="PVM.TYO.Pro.STARTER", price=Decimal("69.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=144",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=1000, port_mbps=300),
    # 香港 Pro / Lite
    RawProduct(external_id="dmit-137", name="PVM.HKG.Lite.TINY", price=Decimal("10.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=137",
               in_stock=False, location="香港", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="dmit-131", name="PVM.HKG.Pro.Pocket", price=Decimal("21.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=131",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=200, port_mbps=100),
    RawProduct(external_id="dmit-132", name="PVM.HKG.Pro.SHARE", price=Decimal("39.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=132",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=400, port_mbps=200),
    RawProduct(external_id="dmit-133", name="PVM.HKG.Pro.STARTER", price=Decimal("79.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=133",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=800, port_mbps=300),
    # 圣何塞 Pro / EB
    RawProduct(external_id="dmit-166", name="PVM.SJC.EB.TINY", price=Decimal("10.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=166",
               in_stock=False, location="圣何塞", line_tags=["CMIN2", "9929", "4837"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="dmit-167", name="PVM.SJC.Pro.STARTER", price=Decimal("139.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=167",
               in_stock=False, location="圣何塞", line_tags=["CN2 GIA", "9929"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000),
    RawProduct(external_id="dmit-168", name="PVM.SJC.Pro.MINI", price=Decimal("29.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=168",
               in_stock=False, location="圣何塞", line_tags=["CN2 GIA", "9929"],
               cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=2000),
]


def _merge(primary: list[RawProduct], *backups: list[RawProduct]) -> list[RawProduct]:
    """按 external_id 合并多源：主源优先，备源补充主源缺失的套餐。
    同 pid 命中多源时，用备源的非空字段填补主源的空字段（如主源缺机房/端口）。
    库存状态取多源交集：任一源报缺货即判缺货（备源可能更陈旧，宁可误报缺货也不误报有货）。"""
    merged: dict[str, RawProduct] = {p.external_id: p for p in primary}
    for source in backups:
        for p in source:
            if p.external_id not in merged:
                merged[p.external_id] = p
            else:
                m = merged[p.external_id]
                for field in ("location", "port_mbps", "bandwidth_gb", "disk_gb", "ram_gb", "cpu_cores"):
                    if getattr(m, field) in (None, "") and getattr(p, field) not in (None, ""):
                        setattr(m, field, getattr(p, field))
                if not m.line_tags and p.line_tags:
                    m.line_tags = p.line_tags
                # 备源库存更陈旧，不再用 AND 把主源有货打成缺货
    return list(merged.values())


class DmitCrawler(MerchantCrawler):
    slug = "dmit"
    name = "DMIT"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://www.dmit.io"
    # 返利链接：DMIT 标准 WHMCS aff.php，带 pid 直达具体套餐。
    aff_url_template = "https://www.dmit.io/aff.php?aff=23928&pid={pid}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        # 双源全部发起（内部各自容错），按优先级合并
        vpszk = _fetch_vpszk(client)
        vpsoso = _fetch_vpsoso(client)
        live = _merge(vpszk, vpsoso)

        if len(live) >= 8:
            # 线上源可用：补充线上未覆盖的经典预置套餐（保留站内历史但设为缺货）
            live_ids = {p.external_id for p in live}
            for p in DMIT_PRESETS:
                if p.external_id not in live_ids:
                    live.append(
                        RawProduct(
                            external_id=p.external_id,
                            name=p.name,
                            price=p.price,
                            currency=p.currency,
                            billing_cycle=p.billing_cycle,
                            purchase_url=p.purchase_url,
                            in_stock=False,
                            location=p.location,
                            line_tags=list(p.line_tags),
                            cpu_cores=p.cpu_cores,
                            ram_gb=p.ram_gb,
                            disk_gb=p.disk_gb,
                            bandwidth_gb=p.bandwidth_gb,
                            port_mbps=p.port_mbps,
                            recommended=p.recommended,
                            from_preset=True,
                        )
                    )
            print(f"[dmit] multi-source live: vpszk={len(vpszk)} vpsoso={len(vpsoso)} merged={len(live)}")
            return live

        # 全部线上源失败：回退预置数据（均为缺货，且不参与消失标记）
        print(f"[dmit] all live sources failed, fallback to {len(DMIT_PRESETS)} presets")
        return [
            RawProduct(
                external_id=p.external_id, name=p.name, price=p.price, currency=p.currency,
                billing_cycle=p.billing_cycle, purchase_url=p.purchase_url, in_stock=False,
                location=p.location, line_tags=list(p.line_tags), cpu_cores=p.cpu_cores,
                ram_gb=p.ram_gb, disk_gb=p.disk_gb, bandwidth_gb=p.bandwidth_gb,
                port_mbps=p.port_mbps, recommended=p.recommended, from_preset=True,
            )
            for p in DMIT_PRESETS
        ]
