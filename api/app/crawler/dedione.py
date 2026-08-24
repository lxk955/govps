"""DediOne 适配器。官网 https://dedione.com （WHMCS lagom 主题）。

分组 URL 已对照官网导航确认（2026-08）。
"""

import httpx

from .base import MerchantCrawler, RawProduct
from .whmcs import GroupPage, crawl_groups


class DediOneCrawler(MerchantCrawler):
    slug = "dedione"
    name = "DediOne"
    # P7 分级调度默认值（分钟）：见 docs/refactor-plan.md §10 P7 频率配置表
    default_interval_minutes = 60
    website = "https://dedione.com"
    aff_url_template = None

    PAGES = [
        GroupPage("https://dedione.com/store/special-vps-plans", None, []),
        GroupPage("https://dedione.com/store/los-angeles-kvm-vps-cn2gia", "洛杉矶", ["CN2 GIA"]),
        GroupPage("https://dedione.com/store/los-angeles-kvm-vps-cn", "洛杉矶", ["CN2 GT"]),
        GroupPage("https://dedione.com/store/los-angeles-kvm-vps-cmin2-cuii", "洛杉矶", ["CMIN2"]),
        GroupPage("https://dedione.com/store/los-angeles-kvm-vps-global", "洛杉矶", ["国际线路"]),
        GroupPage("https://dedione.com/store/kansas-city-kvm-vps-cn2gia", "美国堪萨斯", ["CN2 GIA"]),
        GroupPage("https://dedione.com/store/kansas-city-kvm-vps-cn", "美国堪萨斯", ["CN2 GT"]),
        GroupPage("https://dedione.com/store/kansas-city-kvm-vps-cmin2cuii", "美国堪萨斯", ["CMIN2"]),
        GroupPage("https://dedione.com/store/kansas-city-kvm-vps-global", "美国堪萨斯", ["国际线路"]),
    ]

    def fetch(self, client: httpx.Client) -> list[RawProduct]:
        raws = crawl_groups(client, self.PAGES, self.website)
        for r in raws:
            if "LAX.VPS.CN2" in r.name or (float(r.price) == 59.0 and "CN2" in r.name):
                r.recommended = True
        return raws
