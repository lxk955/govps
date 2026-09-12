"""DMIT 适配器。官网 https://www.dmit.io（WHMCS，Cloudflare 强盾无法直连）。

多源冗余策略（按官方 WHMCS pid 匹配合并，取字段最优）：
1. d-vps.com          —— 结构化 JSON（WASM 解密，97 款套餐 + 官方真实 PID），主源
2. monitor.vpszk.com  —— 结构化 JSON（全量分页抓取，81 款套餐 + 官方真实 PID），备源
3. vpsoso.com         —— 仅当线上结构化源全不可用时兜底
4. DMIT_PRESETS       —— 预置元数据最终回退（20 款权威官方套餐，缺货悲观态）
"""

import re
import time
from decimal import Decimal

import httpx
from selectolax.parser import HTMLParser

from ..config import settings
from .base import MerchantCrawler, RawProduct, extract_line_tags, normalize_location

_CYCLE_CN = {
    "月付": "monthly",
    "季付": "quarterly",
    "半年付": "semi-annually",
    "年付": "annually",
    "两年付": "biennially",
}


def _detect_dmit_lines(name: str, raw_tags: list[str] | str = "") -> list[str]:
    """统一清洗 DMIT 各系列线路标签：
    - Pro 系列 / AN4/AN5/AS3 Pro -> CN2 GIA
    - EB 系列 / Eyeball -> CMIN2, 9929
    - T1 系列 / Lite -> 国际线路
    """
    raw_str = " ".join(raw_tags) if isinstance(raw_tags, list) else str(raw_tags)
    combined = f"{name} {raw_str}".lower()
    if "pro" in combined or "gia" in combined:
        return ["CN2 GIA"]
    if "eb" in combined or "eyeball" in combined or "9929" in combined or "cmin2" in combined:
        tags = ["CMIN2", "9929"]
        if "4837" in combined:
            tags.append("4837")
        return tags
    if "t1" in combined or "lite" in combined or "国际" in combined:
        return ["国际线路"]
    return extract_line_tags(combined)


# ── 源 1：d-vps.com（结构化实时源，真实官方 PID）──
def _fetch_dvps(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    try:
        from .dvps_source import DvpsSource

        dvps_prods = DvpsSource().fetch_products("dmit", client)
        for dp in dvps_prods:
            pid = dp.external_id
            clean_pid = str(pid).replace("dmit-", "")
            name = dp.name
            line_tags = _detect_dmit_lines(name, dp.line_tags)
            products.append(
                RawProduct(
                    external_id=f"dmit-{clean_pid}",
                    name=name,
                    price=dp.price,
                    currency=dp.currency,
                    billing_cycle=dp.billing_cycle,
                    price_options=dp.price_options,
                    purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={clean_pid}",
                    in_stock=dp.in_stock,
                    location=dp.location,
                    line_tags=line_tags,
                    cpu_cores=dp.cpu_cores,
                    ram_gb=dp.ram_gb,
                    disk_gb=dp.disk_gb,
                    bandwidth_gb=dp.bandwidth_gb,
                    port_mbps=dp.port_mbps,
                    stock_verified=True,
                )
            )
    except Exception as e:
        print(f"[dmit] dvps feed notice: {e}")
    return products


# ── 源 2：monitor.vpszk.com（结构化 JSON，分页抓取，真实官方 PID）──
def _fetch_vpszk(client: httpx.Client) -> list[RawProduct]:
    products: list[RawProduct] = []
    try:
        page = 1
        while True:
            resp = client.get(
                "https://monitor.vpszk.com/api/plans",
                params={"page": page, "pageSize": 100},
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            items = [p for p in data.get("items", []) if p.get("providerSlug") == "dmit"]
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
                name = p.get("name") or f"DMIT {pid}"
                line_tags = _detect_dmit_lines(name, p.get("tags") or [])
                products.append(
                    RawProduct(
                        external_id=f"dmit-{pid}",
                        name=name,
                        price=dec_price,
                        currency=p.get("currency") or "USD",
                        billing_cycle=cycle,
                        purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={pid}",
                        in_stock=p.get("stock") == "in",
                        location=normalize_location(city or ""),
                        line_tags=line_tags,
                        cpu_cores=p.get("vcpu"),
                        ram_gb=Decimal(str(p["ramGb"])) if p.get("ramGb") else None,
                        disk_gb=p.get("diskGb"),
                        bandwidth_gb=p.get("trafficGb"),
                        port_mbps=p.get("portMbps"),
                        stock_verified=True,
                    )
                )
            total_pages = data.get("totalPages", 1)
            if page >= total_pages or not data.get("items"):
                break
            page += 1
    except Exception as e:
        print(f"[dmit] vpszk feed notice: {e}")
    return products


# ── 源 3：vpsoso.com（HTML 表格兜底）──
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
            line_tags = _detect_dmit_lines(raw_name, cells[4])

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
            pid_match = re.search(r"pid=(\d+)", href) or re.search(r"[?&]id=(\d+)", href)
            v_id = pid_match.group(1) if pid_match else None
            if not v_id:
                continue

            p_name = raw_name if raw_name.startswith("PVM.") else f"PVM.{raw_name}"
            products.append(
                RawProduct(
                    external_id=f"dmit-{v_id}",
                    name=p_name,
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


# ── 预置 DMIT 官方 20 款真实权威经典套餐（最终回退，预置默认均为缺货）──
DMIT_PRESETS: list[RawProduct] = [
    # 洛杉矶 Pro 旗舰（三网 CN2 GIA）
    RawProduct(external_id="dmit-183", name="PVM.LAX.Pro.WEE", price=Decimal("39.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=183",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=10, bandwidth_gb=450, port_mbps=500, recommended=True),
    RawProduct(external_id="dmit-253", name="PVM.LAX.AS3.Pro.TINY", price=Decimal("10.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=253",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=1000, port_mbps=1000, recommended=True),
    RawProduct(external_id="dmit-254", name="PVM.LAX.AS3.Pro.Pocket", price=Decimal("16.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=254",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=1500, port_mbps=1000),
    RawProduct(external_id="dmit-255", name="PVM.LAX.AS3.Pro.STARTER", price=Decimal("34.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=255",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=2000, port_mbps=2000),
    RawProduct(external_id="dmit-256", name="PVM.LAX.AS3.Pro.MINI", price=Decimal("62.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=256",
               in_stock=False, location="洛杉矶", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=60, bandwidth_gb=3000, port_mbps=2000),
    # 洛杉矶 EB (Eyeball) 系列
    RawProduct(external_id="dmit-188", name="PVM.LAX.EB.WEE", price=Decimal("39.90"), currency="USD",
               billing_cycle="annually", purchase_url="https://www.dmit.io/cart.php?a=add&pid=188",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=15, bandwidth_gb=1000, port_mbps=1000, recommended=True),
    RawProduct(external_id="dmit-259", name="PVM.LAX.AS3.EB.TINY", price=Decimal("10.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=259",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=2000, port_mbps=2000),
    RawProduct(external_id="dmit-260", name="PVM.LAX.AS3.EB.Pocket", price=Decimal("16.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=260",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=3000, port_mbps=2000),
    RawProduct(external_id="dmit-261", name="PVM.LAX.AS3.EB.STARTER", price=Decimal("34.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=261",
               in_stock=False, location="洛杉矶", line_tags=["CMIN2", "9929"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=4000, port_mbps=3000),
    # 洛杉矶 T1 系列
    RawProduct(external_id="dmit-271", name="PVM.LAX.AS3.T1.TINY", price=Decimal("6.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=271",
               in_stock=False, location="洛杉矶", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=2000, port_mbps=1000),
    # 香港 Pro 系列 (CN2 GIA)
    RawProduct(external_id="dmit-265", name="PVM.HKG.AS3.Pro.TINY", price=Decimal("39.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=265",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=300, port_mbps=100, recommended=True),
    RawProduct(external_id="dmit-266", name="PVM.HKG.AS3.Pro.STARTER", price=Decimal("79.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=266",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=600, port_mbps=200),
    RawProduct(external_id="dmit-267", name="PVM.HKG.AS3.Pro.MINI", price=Decimal("126.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=267",
               in_stock=False, location="香港", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=60, bandwidth_gb=1000, port_mbps=300),
    # 香港 T1 系列
    RawProduct(external_id="dmit-198", name="PVM.HKG.AS3.T1.TINY", price=Decimal("6.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=198",
               in_stock=False, location="香港", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="dmit-199", name="PVM.HKG.AS3.T1.STARTER", price=Decimal("12.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=199",
               in_stock=False, location="香港", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=4000, port_mbps=1000),
    # 东京 Pro 系列 (CN2 GIA)
    RawProduct(external_id="dmit-138", name="PVM.TYO.AS3.Pro.TINY", price=Decimal("21.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=138",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=300, port_mbps=100, recommended=True),
    RawProduct(external_id="dmit-139", name="PVM.TYO.AS3.Pro.STARTER", price=Decimal("45.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=139",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("2.0"), disk_gb=40, bandwidth_gb=600, port_mbps=200),
    RawProduct(external_id="dmit-140", name="PVM.TYO.AS3.Pro.MINI", price=Decimal("89.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=140",
               in_stock=False, location="东京", line_tags=["CN2 GIA"],
               cpu_cores=2, ram_gb=Decimal("4.0"), disk_gb=60, bandwidth_gb=1000, port_mbps=300),
    # 东京 T1 系列
    RawProduct(external_id="dmit-131", name="PVM.TYO.AS3.T1.TINY", price=Decimal("6.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=131",
               in_stock=False, location="东京", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("1.0"), disk_gb=20, bandwidth_gb=2000, port_mbps=1000),
    RawProduct(external_id="dmit-132", name="PVM.TYO.AS3.T1.STARTER", price=Decimal("12.90"), currency="USD",
               billing_cycle="monthly", purchase_url="https://www.dmit.io/cart.php?a=add&pid=132",
               in_stock=False, location="东京", line_tags=["国际线路"],
               cpu_cores=1, ram_gb=Decimal("2.0"), disk_gb=30, bandwidth_gb=4000, port_mbps=1000),
]


def _merge(primary: list[RawProduct], *backups: list[RawProduct]) -> list[RawProduct]:
    """按 external_id 合并多源：主源优先，备源补充缺失套餐与非空字段。"""
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
                if p.stock_verified and not m.stock_verified:
                    m.in_stock = p.in_stock
                    m.stock_verified = True
    return list(merged.values())


def _parse_dmit_html(pid: str, html: str) -> RawProduct | None:
    """解析 DMIT 官方 WHMCS 订购页面 (cart.php?a=add&pid={pid})。"""
    if not html:
        return None
    lower = html.lower()
    if "out of stock on this item" in lower or "<h1>out of stock</h1>" in lower or "out of stock" in lower:
        # 官方返回缺货
        for pre in DMIT_PRESETS:
            if pre.external_id == f"dmit-{pid}":
                return RawProduct(
                    external_id=f"dmit-{pid}",
                    name=pre.name,
                    price=pre.price,
                    currency=pre.currency,
                    billing_cycle=pre.billing_cycle,
                    purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={pid}",
                    in_stock=False,
                    location=pre.location,
                    line_tags=list(pre.line_tags),
                    cpu_cores=pre.cpu_cores,
                    ram_gb=pre.ram_gb,
                    disk_gb=pre.disk_gb,
                    bandwidth_gb=pre.bandwidth_gb,
                    port_mbps=pre.port_mbps,
                    recommended=pre.recommended,
                    stock_verified=True,
                    from_preset=False,
                )
        return RawProduct(
            external_id=f"dmit-{pid}",
            name=f"DMIT {pid}",
            price=Decimal("0"),
            currency="USD",
            billing_cycle="monthly",
            purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={pid}",
            in_stock=False,
            stock_verified=True,
            from_preset=False,
        )

    # 官方返回配置页面（有货）
    if "frmConfigureProduct" not in html and "cart-products-title" not in html:
        return None

    title_m = re.search(r"class=[\x27\x22]cart-products-title[\x27\x22][^>]*>(.*?)</div>", html, re.S)
    raw_name = title_m.group(1).strip() if title_m else f"DMIT {pid}"
    name = raw_name if raw_name.startswith("PVM.") else f"PVM.{raw_name}"

    price_m = re.search(r"class=[\x27\x22]price-num[\x27\x22][^>]*>\s*([\d\.]+)\s*</div>", html)
    price = Decimal(price_m.group(1).strip()) if price_m else Decimal("0")

    cycle_m = re.search(r"class=[\x27\x22]billing-cycle-text[\x27\x22][^>]*>.*?([A-Za-z]+)\s*</div>", html, re.S)
    raw_cycle = cycle_m.group(1).lower() if cycle_m else "monthly"
    cycle = {
        "monthly": "monthly",
        "quarterly": "quarterly",
        "semiannually": "semi-annually",
        "annually": "annually",
        "biennially": "biennially",
    }.get(raw_cycle, "monthly")

    # 规格提取
    titles = re.findall(r"desc-item-title[\x27\x22][^>]*>(.*?)</div>", html, re.S)
    values = re.findall(r"desc-item-value[\x27\x22][^>]*>(.*?)</div>", html, re.S)
    specs = {t.strip(): v.strip() for t, v in zip(titles, values)}

    cpu_cores = None
    if "vCPU" in specs:
        m = re.search(r"(\d+)", specs["vCPU"])
        if m:
            cpu_cores = int(m.group(1))

    ram_gb = None
    if "RAM" in specs:
        m = re.search(r"([\d\.]+)", specs["RAM"])
        if m:
            ram_gb = Decimal(m.group(1))

    disk_gb = None
    if "Storage" in specs:
        m = re.search(r"(\d+)", specs["Storage"])
        if m:
            disk_gb = int(m.group(1))

    quota_m = re.search(r"class=[\x27\x22]highspeed-quota[\x27\x22][^>]*>\s*(\d+)\s*(GB|TB|G|T)", html, re.S)
    bandwidth_gb = None
    if quota_m:
        val = int(quota_m.group(1))
        unit = quota_m.group(2).upper()
        bandwidth_gb = val * 1000 if "T" in unit else val

    port_m = re.search(r"class=[\x27\x22]highspeed-text[\x27\x22][^>]*>.*?(\d+)\s*(Gbps|Mbps|G|M)", html, re.S)
    port_mbps = None
    if port_m:
        val = int(port_m.group(1))
        unit = port_m.group(2).upper()
        port_mbps = val * 1000 if "G" in unit else val

    city = None
    if "HKG" in name:
        city = "香港"
    elif "LAX" in name:
        city = "洛杉矶"
    elif "TYO" in name:
        city = "东京"
    elif "SJC" in name:
        city = "圣何塞"
    loc = normalize_location(city or "")

    line_tags = _detect_dmit_lines(name, specs.get("Routing Profile", ""))

    return RawProduct(
        external_id=f"dmit-{pid}",
        name=name,
        price=price,
        currency="USD",
        billing_cycle=cycle,
        purchase_url=f"https://www.dmit.io/cart.php?a=add&pid={pid}",
        in_stock=True,
        location=loc,
        line_tags=line_tags,
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        disk_gb=disk_gb,
        bandwidth_gb=bandwidth_gb,
        port_mbps=port_mbps,
        stock_verified=True,
        from_preset=False,
    )


def _fetch_official_dmit(target_pids: list[str]) -> list[RawProduct]:
    """通过 FlareSolverr 直接抓取官方 WHMCS 订购页面一手数据。"""
    if not settings.FLARESOLVERR_URL.strip():
        return []
    try:
        from .solver import flaresolverr_session

        session_name = f"dmit_{int(time.time())}"
        products: list[RawProduct] = []
        with flaresolverr_session(session_name) as (solver, sid):
            if not solver or not sid:
                return []
            for pid in target_pids:
                url = f"https://www.dmit.io/cart.php?a=add&pid={pid}"
                html = solver.fetch(url, session_id=sid, timeout=20.0)
                if html:
                    p = _parse_dmit_html(pid, html)
                    if p:
                        products.append(p)
        if products:
            print(f"[dmit] official store scraping succeeded: {len(products)} products verified")
        return products
    except Exception as e:
        print(f"[dmit] official store scraping notice: {e}")
        return []


class DmitCrawler(MerchantCrawler):
    slug = "dmit"
    name = "DMIT"
    default_interval_minutes = 5
    website = "https://www.dmit.io"
    aff_url_template = "https://www.dmit.io/aff.php?aff=23928&pid={pid}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        # 1. 尝试三方监控源获取全量候选套餐
        dvps = _fetch_dvps(client)
        vpszk = _fetch_vpszk(client)
        live = _merge(dvps, vpszk)
        vpsoso: list[RawProduct] = []
        if len(live) < 8:
            vpsoso = _fetch_vpsoso(client)
            live = _merge(live, vpsoso)

        # 2. 若配置了 FlareSolverr，从官方网站抓取一手数据覆盖/验证核心及有货套餐
        if settings.FLARESOLVERR_URL.strip():
            candidate_pids = [p.external_id.replace("dmit-", "") for p in DMIT_PRESETS]
            for p in live:
                clean_id = p.external_id.replace("dmit-", "")
                if p.in_stock and clean_id not in candidate_pids:
                    candidate_pids.append(clean_id)

            official_products = _fetch_official_dmit(candidate_pids[:30])
            if official_products:
                live = _merge(official_products, live)

        if len(live) >= 8:
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
            print(f"[dmit] multi-source live: dvps={len(dvps)} vpszk={len(vpszk)} vpsoso={len(vpsoso)} merged={len(live)}")
            return live

        print(f"[dmit] all live sources failed, fallback to {len(DMIT_PRESETS)} presets")
        return [
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
            for p in DMIT_PRESETS
        ]
