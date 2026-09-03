"""WHMCS 商店页通用解析器 v2（已对照 DediOne 等真实页面校准）。

WHMCS 标准商店卡片结构（lagom / twenty-one 等主题通用）：
  <div class="package" id="product{pid}">
    <h3 class="package-title">套餐名</h3>
    <div class="price-amount">$12.99 USD</div>
    <div class="price-cycle">Annually</div>
    <a class="btn-order-now {disabled}" href="/store/xxx/slug">Order Now</a>
    <div class="package-qty">N Available</div>
  </div>
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from selectolax.parser import HTMLParser, Node

from .base import RawProduct, extract_line_tags, extract_location, parse_specs, slugify

_RE_PRICE = re.compile(
    r"([$€£¥])?\s*(\d+(?:[.,]\d{1,2})?)\s*(USD|EUR|GBP|CNY|HKD|CAD|AUD|SGD|JPY|KRW)?", re.I
)
_RE_PID = re.compile(r"pid=(\d+)")
_RE_PRODUCT_ID = re.compile(r"^product(\d+)$")
_RE_AVAILABLE = re.compile(r"(\d+)\s*(?:Available|个可用|可用)", re.I)

# 缺货文案（中英多语言，覆盖 WHMCS 常见主题表达）
_OOS_KEYWORDS = (
    "out of stock",
    "sold out",
    "currently unavailable",
    "temporarily unavailable",
    "not available",
    "缺货",
    "售罄",
    "已售完",
    "售完",
    "暂无库存",
    "无货",
    "补货中",
)

_CURRENCY_MAP = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "CNY"}

_CYCLE_KEYWORDS = [
    ("triennial", "triennially"),
    ("biennial", "biennially"),
    ("semi-annual", "semi-annually"),
    ("semiannual", "semi-annually"),
    ("semi_annual", "semi-annually"),
    ("semi", "semi-annually"),
    ("half-year", "semi-annually"),
    ("half year", "semi-annually"),
    ("half", "semi-annually"),
    ("annual", "annually"),
    ("year", "annually"),
    ("/yr", "annually"),
    ("quarter", "quarterly"),
    ("month", "monthly"),
    ("/mo", "monthly"),
]

# 「1000 GB Monthly Transfer」这类流量描述不能当成付款周期
_RE_TRANSFER_NOISE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:gb?|tb?)\s*(?:monthly|per\s*month|/mo)?\s*(?:transfer|bandwidth|traffic|流量)",
    re.I,
)


@dataclass
class GroupPage:
    url: str
    location: str | None = None
    line_tags: list[str] = field(default_factory=list)


def detect_cycle(text: str) -> str:
    if not text or not str(text).strip():
        return "annually"
    low = _RE_TRANSFER_NOISE.sub(" ", text).lower()
    for kw, cycle in _CYCLE_KEYWORDS:
        if kw in low:
            return cycle
    return "annually"


def _parse_price(text: str) -> tuple[Decimal | None, str]:
    """从 '$12.99 USD' 之类文本提取价格与币种。"""
    m = _RE_PRICE.search(text)
    if not m:
        return None, "USD"
    try:
        price = Decimal(m.group(2).replace(",", ""))
    except InvalidOperation:
        return None, "USD"
    currency = (m.group(3) or _CURRENCY_MAP.get(m.group(1) or "", "USD")).upper()
    return price, currency


def _text(node: Node | None) -> str:
    return node.text(separator=" ", strip=True) if node else ""


def _first(card: Node, selectors: str) -> Node | None:
    return card.css_first(selectors)


def parse_store_page(html: str, group: GroupPage, base_url: str) -> list[RawProduct]:
    tree = HTMLParser(html)
    products: list[RawProduct] = []

    cards = tree.css("div.package, div.product")
    for card in cards:
        name = _text(_first(card, ".package-title, .product-name, .plan-name, h3"))
        if not name:
            continue

        # 价格：优先结构化节点，退化到卡片全文
        price_text = _text(_first(card, ".price-amount, .price"))
        price, currency = _parse_price(price_text)
        if price is None:
            price, currency = _parse_price(card.text(separator=" ", strip=True))
        if price is None:
            continue

        cycle_text = _text(_first(card, ".price-cycle"))
        billing_cycle = detect_cycle(cycle_text)

        # 库存判定（正向确认原则：拿到明确可购买证据才判有货，证据不足一律判缺货，
        # 防止主题改版导致选择器失配时静默显示有货）
        order_btn = _first(
            card, "a.btn-order-now, a[href*='pid='], a[href*='/cart/'], button[type='submit']"
        )
        btn_class = (order_btn.attributes.get("class", "") if order_btn else "") or ""
        btn_disabled_attr = order_btn.attributes.get("disabled") if order_btn else None
        qty_text = _text(_first(card, ".package-qty, .qty"))
        qty_match = _RE_AVAILABLE.search(qty_text)
        card_text = card.text(separator=" ", strip=True).lower()

        has_oos_signal = (
            "disabled" in btn_class
            or btn_disabled_attr is not None
            or (qty_match is not None and int(qty_match.group(1)) == 0)
            or any(kw in card_text for kw in _OOS_KEYWORDS)
        )
        has_stock_signal = (
            qty_match is not None and int(qty_match.group(1)) > 0
        ) or (order_btn is not None and "disabled" not in btn_class and btn_disabled_attr is None)
        in_stock = has_stock_signal and not has_oos_signal

        # 产品 ID：div id="product249" 优先，其次订购链接里的 pid
        external_id = ""
        dom_id = card.attributes.get("id", "") or ""
        if m := _RE_PRODUCT_ID.match(dom_id):
            external_id = m.group(1)
        href = order_btn.attributes.get("href", "") if order_btn else ""
        if not external_id and (m := _RE_PID.search(href)):
            external_id = m.group(1)
        if not external_id:
            external_id = slugify(name)

        # 加购链接优先用 WHMCS 标准 cart.php?a=add&pid=xxx：
        # 页面里的 slug 链接（/store/xxx/yyy）经常因官网改版而失效/被重定向到列表页，
        # 而 pid 加购链接在实测中对 DediOne 等商家稳定有效。
        if external_id and external_id.isdigit():
            purchase_url = f"{base_url}/cart.php?a=add&pid={external_id}"
        else:
            purchase_url = href or group.url
            if purchase_url.startswith("/"):
                purchase_url = base_url.rstrip("/") + purchase_url

        full_text = card.text(separator=" ", strip=True)
        p = RawProduct(
            external_id=external_id,
            name=name[:250],
            price=price,
            currency=currency,
            billing_cycle=billing_cycle,
            purchase_url=purchase_url,
            in_stock=in_stock,
            location=group.location or extract_location(full_text),
            line_tags=list(group.line_tags),
        )
        parse_specs(full_text, p)
        # 从规格描述文本补充线路标签（如 "9929 Advanced Network Routing"）
        for tag in extract_line_tags(full_text):
            if tag not in p.line_tags:
                p.line_tags.append(tag)
        products.append(p)

    return products


def crawl_groups(client, pages: list[GroupPage], base_url: str) -> list[RawProduct]:
    results: list[RawProduct] = []
    errors: list[str] = []
    for group in pages:
        try:
            resp = client.get(group.url)
            resp.raise_for_status()
        except Exception as e:
            errors.append(f"{group.url}: {e}")
            continue
        results.extend(parse_store_page(resp.text, group, base_url))
    if errors and not results:
        raise RuntimeError("; ".join(e[:150] for e in errors))
    return results
