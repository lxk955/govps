"""列表域纯计算函数（P1 自 routers/products.py 原样平移，公式与语义零改动）。

迁移原因（AGENTS.md Backend：业务逻辑不放在路由层）：
- 评分/聚合键/搜索文本同时被「请求期旧实现（影子比对基准）」与
  「扫描期物化（services/materialize.py）」两个调用方共享，必须单一定义源。
- 函数体保持与平移前逐字节一致；调用方需在 Session 内传入 ORM 对象
  （p.merchant 懒加载可用）。
"""

import re

from ..schemas import yearly_price


_RE_DATE_PREFIX = re.compile(r"^\d{6,8}-")
_RE_PRICE_SUFFIX = re.compile(r"-?\d+\.\d{2}$")
_RE_PVM_PREFIX = re.compile(r"(?i)^pvm\.")  # DMIT 双数据源重复行：vpsoso 源带 PVM. 前缀
_RE_CYCLE_TOKENS = re.compile(
    r"(?i)[\s_-]*(annually?|monthly|quarterly|semi[-_]?annually?|biennially|triennially|year|yr|month|mo|年付|月付|季付|半年付|两年付|三年付)[\s_-]*"
)


def _normalize_group_name(name: str) -> str:
    """聚合用规范化名称：去除日期前缀、价格后缀与付款周期词，
    使同款不同周期的套餐（如 DediOne 月付/年付两个 pid）能聚合为一张卡片，
    而不同产品线（如 ZgoCloud ISP vs Optimised、DMIT AS3 vs Lite）不会被误合并。"""
    n = _RE_DATE_PREFIX.sub("", name or "").strip()
    n = _RE_PRICE_SUFFIX.sub("", n).strip("- ")
    n = _RE_PVM_PREFIX.sub("", n)
    n = _RE_CYCLE_TOKENS.sub(" ", n)
    return " ".join(n.lower().split())


POPULAR_LOCATIONS = {"洛杉矶", "东京", "香港", "新加坡", "圣何塞"}
PREMIUM_LINES = {"CN2 GIA", "9929", "CMIN2"}
OPTIMIZED_LINES = {"4837", "CN2 GT"}


def calculate_scores_and_reasons(
    p,
    watch_count: int = 0,
    total_clicks: int = 0,
    clicks_7d: int = 0,
    clicks_3h: int = 0,
    is_recent_restock: bool = False,
    is_recent_drop: bool = False,
) -> tuple[float, float, float, list[str]]:
    """计算客观值得买指数 (Deal Score)、活跃热度指数 (Popularity Score)、综合推荐指数 (Hot Score) 以及可解释推荐理由 (Reasons)。"""
    deal_score = 0.0
    popularity_score = 0.0
    reasons: list[str] = []

    # === 一、Deal Score (客观值得买指数，主导 70% 权重) ===
    # 1. 线路品质 (CN2 GIA / 9929 / CMIN2 顶级精品专线)
    tags = set(p.line_tags or [])
    if tags & PREMIUM_LINES:
        deal_score += 45.0
        reasons.append("三网 GIA/9929 顶级专线")
    elif tags & OPTIMIZED_LINES:
        deal_score += 25.0
        reasons.append("优化直连线路")

    # 2. 价格与性价比 (折算年付价格)
    yp = yearly_price(p.price, p.billing_cycle)
    if yp <= 36.0:
        deal_score += 40.0
        reasons.append("超低门槛年付")
    elif yp <= 60.0:
        deal_score += 25.0
        reasons.append("年付高性价比")
    elif yp <= 100.0:
        deal_score += 15.0

    # 3. 硬件规格亮点 (如 7950X, >=1Gbps 大带宽, 大内存)
    name_lower = (p.name or "").lower()
    if "7950x" in name_lower or "7900x" in name_lower:
        deal_score += 20.0
        reasons.append("AMD 7950X 顶级核")
    if p.port_mbps and p.port_mbps >= 1000:
        deal_score += 15.0
        reasons.append("1Gbps+ 大带宽")
    if p.ram_gb and p.ram_gb >= 2.0 and yp <= 60.0:
        deal_score += 15.0
        reasons.append("大内存高配")

    # 4. 降价与史低
    if is_recent_drop:
        deal_score += 40.0
        reasons.append("近48h 降价")
    elif p.prev_price is not None and p.price < p.prev_price:
        deal_score += 20.0
        reasons.append("降价中")

    # 5. 现货状态与最新补货
    if p.in_stock:
        deal_score += 30.0
        reasons.append("当前有货")
    else:
        deal_score -= 30.0  # 缺货显著降权

    if is_recent_restock and p.in_stock:
        deal_score += 35.0
        reasons.append("刚刚补货")

    # 6. 精选推荐标识
    if p.recommended:
        deal_score += 35.0
        reasons.append("精选推荐款")

    # 7. 冷启动探索机制 (Exploration Bonus - 消除马太效应，扶持低曝光但高性价比的好 SKU)
    if total_clicks <= 5 and p.in_stock and (tags & PREMIUM_LINES or yp <= 60.0):
        deal_score += 25.0
        reasons.append("高性价比潜力款")

    # === 二、Popularity Score (大众活跃热度，占比 30% 权重) ===
    popularity_score += min(watch_count, 10) * 12.0
    popularity_score += clicks_3h * 20.0
    popularity_score += clicks_7d * 6.0
    popularity_score += min(total_clicks, 50) * 1.5

    if clicks_3h >= 2 or clicks_7d >= 8 or watch_count >= 3:
        reasons.append("近期热门关注")

    # 综合得分 (Deal Score 70% + Popularity 30%)
    hot_score = deal_score * 0.7 + popularity_score * 0.3

    # 去重并精简推荐理由
    dedup_reasons: list[str] = []
    for r in reasons:
        if r not in dedup_reasons:
            dedup_reasons.append(r)

    return round(deal_score, 1), round(popularity_score, 1), round(hot_score, 1), dedup_reasons[:4]


def is_historical_low(price, snapshot_min) -> bool:
    """当前价是否等于（或低于）历史快照最低价。与「相对上次降价」的 price_dropped 不同。"""
    if price is None or snapshot_min is None:
        return False
    try:
        return float(price) <= float(snapshot_min) + 1e-9
    except (TypeError, ValueError):
        return False


def spec_group_key(p) -> tuple:
    return (
        p.merchant_id,
        _normalize_group_name(p.name),
        p.location or "",
        tuple(sorted(p.line_tags or [])),
        p.cpu_cores or 0,
        float(p.ram_gb or 0),
        p.disk_gb or 0,
        p.bandwidth_gb or 0,
    )


def _product_search_text(p) -> str:
    """构建产品全量可搜索文本，支持别名、多维度中英文模糊搜索。"""
    parts = [
        p.name or "",
        p.merchant.name if p.merchant else "",
        p.merchant.slug if p.merchant else "",
        p.location or "",
        " ".join(p.line_tags or []),
    ]
    # 商家常用别名
    m_slug = p.merchant.slug if p.merchant else ""
    if m_slug == "bandwagon":
        parts.append("搬瓦工 瓦工 bwh bwh88 bwh81 bwh9")
    elif m_slug == "dmit":
        parts.append("大妈")
    elif m_slug == "zgocloud":
        parts.append("zgo 芝戈")
    elif m_slug == "dedione":
        parts.append("dedi")
    elif m_slug == "vps":
        parts.append("v.ps xtom vps")
    elif m_slug == "vmiss":
        parts.append("vmiss v miss 加拿大")
    elif m_slug == "66yun":
        parts.append("66云 六六云 666clouds 66cloud 66")

    # 机房/地区别名
    loc = (p.location or "").lower()
    if "洛杉矶" in loc or "lax" in loc:
        parts.append("lax los angeles 美西 加州 洛杉矶")
    elif "圣何塞" in loc or "sjc" in loc:
        parts.append("sjc san jose 圣何塞")
    elif "东京" in loc or "tyo" in loc:
        parts.append("tyo tokyo 日本 东京 日本东京")
    elif "香港" in loc or "hkg" in loc:
        parts.append("hkg hk 中国香港 香港")
    elif "大阪" in loc or "kix" in loc:
        parts.append("kix osaka 日本 大阪 日本大阪")
    elif "新加坡" in loc or "sin" in loc:
        parts.append("sin singapore 新加坡")
    elif "法兰克福" in loc or "fra" in loc:
        parts.append("fra frankfurt 德国 法兰克福")
    elif "堪萨斯" in loc or "kc" in loc:
        parts.append("kansas missouri 堪萨斯 密苏里")

    # 硬件与网络参数搜索支持（如 1c 1g 10g 1t 无限流量 等）
    if p.cpu_cores:
        parts.append(f"{p.cpu_cores}核 {p.cpu_cores}c {p.cpu_cores}core {p.cpu_cores}vcpu")
    if p.ram_gb:
        ram_int = int(p.ram_gb * 1024)
        parts.append(f"{p.ram_gb}g {p.ram_gb}gb {ram_int}m {ram_int}mb 内存")
    if p.disk_gb:
        parts.append(f"{p.disk_gb}g {p.disk_gb}gb 硬盘 ssd nvme")
    if p.bandwidth_gb:
        if p.bandwidth_gb < 0:
            parts.append("无限流量 不限流量 unlimited")
        elif p.bandwidth_gb >= 1000:
            tb = p.bandwidth_gb / 1000
            tb_str = f"{tb:.0f}t" if p.bandwidth_gb % 1000 == 0 else f"{tb:.1f}t"
            parts.append(f"{p.bandwidth_gb}g {tb_str} 流量")
        else:
            parts.append(f"{p.bandwidth_gb}g 流量")

    return " ".join(parts).lower()
