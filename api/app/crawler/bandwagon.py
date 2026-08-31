"""搬瓦工 BandwagonHost 适配器。官网 https://bwh81.net。

搬瓦工套餐页由 JS 驱动，但官方暴露了完整 JSON 数据源：
  GET https://bwh81.net/order/get-data
字段齐全（配置、多周期价格、outOfStock、机房），无需解析 HTML。
"""

from decimal import Decimal

import httpx

from .base import MerchantCrawler, RawProduct, normalize_location, normalize_line_tags

DATA_URL = "https://bwh81.net/order/get-data"
CART_URL = "https://bwh81.net/cart.php?a=add&pid={pid}&billingcycle={cycle}"

_PERIOD_MAP = {
    "monthly": "monthly",
    "quarterly": "quarterly",
    "semi-annually": "semi-annually",
    "annually": "annually",
    "biennially": "biennially",
    "triennially": "triennially",
}

# 优选年付，其次月付（年付是搬瓦工用户最关注的周期）
_PERIOD_PRIORITY = ["annually", "semi-annually", "quarterly", "monthly"]


class BandwagonCrawler(MerchantCrawler):
    slug = "bandwagon"
    name = "BandwagonHost"
    # P7 分级调度默认值（分钟）：2026-08-31 起运营决策全商家统一 5 分钟
    default_interval_minutes = 5
    website = "https://bwh81.net"
    # 搬瓦工官方推荐返利模板 (aff=83019)
    aff_url_template = "https://bwh81.net/aff.php?aff=83019&a=add&pid={pid}"

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        resp = client.get(DATA_URL)
        resp.raise_for_status()
        data = resp.json()

        # 机房 ID → 城市，用于把多机房套餐标注为 "Multi-DC: Los Angeles, Hong Kong 等"
        dc_city: dict[str, str] = {}
        for loc in data.get("locations", []):
            for dc in loc.get("datacenters", []):
                dc_city[dc["id"]] = loc["city"]

        def cities_of(item: dict) -> str | None:
            raw_cities = list(dict.fromkeys(
                dc_city[code] for code in item.get("datacenters", {}) if code in dc_city
            ))
            if not raw_cities:
                return None
            if len(raw_cities) == 1:
                return normalize_location(raw_cities[0])
            return "多机房 (可迁)"

        products: list[RawProduct] = []
        for item in data.get("products", []):
            prices = item.get("prices") or []
            if not prices:
                continue
            chosen = None
            for pref in _PERIOD_PRIORITY:
                chosen = next(
                    (pr for pr in prices if (pr.get("period") or "").lower() == pref), None
                )
                if chosen:
                    break
            if chosen is None:
                chosen = prices[0]

            price_options = []
            for pr in prices:
                p_period = (pr.get("period") or "annually").lower()
                p_cycle = _PERIOD_MAP.get(p_period, "annually")
                p_cents = pr.get("cents") or 0
                price_options.append({
                    "billing_cycle": p_cycle,
                    "price": float(Decimal(p_cents) / 100),
                    "currency": pr.get("currency", "USD"),
                    "purchase_url": CART_URL.format(pid=item["id"], cycle=p_period),
                })

            period = (chosen.get("period") or "annually").lower()
            products.append(
                RawProduct(
                    external_id=str(item["id"]),
                    name=item["name"][:250],
                    price=Decimal(chosen["cents"]) / 100,
                    currency=chosen.get("currency", "USD"),
                    billing_cycle=_PERIOD_MAP.get(period, "annually"),
                    purchase_url=CART_URL.format(pid=item["id"], cycle=period),
                    price_options=price_options,
                    in_stock=not item.get("outOfStock", False),
                    location=cities_of(item),
                    line_tags=normalize_line_tags(item["name"]),
                    cpu_cores=item.get("cpu"),
                    ram_gb=Decimal(item["ram"]) / 1024 if item.get("ram") else None,
                    disk_gb=int(item["ssd"] / 1000) if item.get("ssd") else None,
                    bandwidth_gb=int(item["transfer"] / 1000) if item.get("transfer") else None,
                    port_mbps=item.get("link"),
                )
            )
        return products
