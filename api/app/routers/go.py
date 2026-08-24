import re
from html import escape
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from ..database import get_db
from ..models import AffClick, Product
from .products import _get_product_price_options, group_members

router = APIRouter(tags=["go"])

# ZgoCloud 是定制 WHMCS：加购只能 POST 表单（action=add&id=pid），GET 链接会 404。
# 返回一个自动提交表单的页面，用户无感跳转到官网配置流程。
ZGOCLOUD_POST_URL = "https://clients.zgovps.com/index.php?/cart/"


def _auto_post_page(url: str, fields: dict[str, str]) -> HTMLResponse:
    # 套餐名/产品ID来自商家页面爬取结果，插入 HTML 前必须转义，防止存储型 XSS
    inputs = "".join(
        f'<input type="hidden" name="{escape(name, quote=True)}" value="{escape(value, quote=True)}">'
        for name, value in fields.items()
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>正在跳转到商家…</title></head>
<body>
<form id="auto-submit" method="POST" action="{url}">{inputs}</form>
<script>document.getElementById('auto-submit').submit()</script>
<!-- JS 被禁用时的兜底：手动点击仍可继续 -->
<noscript>
  <p style="text-align:center;font-family:system-ui,sans-serif;">正在为您跳转到商家…</p>
  <div style="text-align:center;">
    <button type="submit" form="auto-submit"
            style="padding:10px 24px;background:#2563eb;color:#fff;border:0;border-radius:8px;
                   font-size:14px;font-weight:600;cursor:pointer;">点击继续前往商家</button>
  </div>
</noscript>
</body>
</html>"""
    return HTMLResponse(html)


def _oos_interstitial(product: Product, target_url: str) -> HTMLResponse:
    """缺货兜底页：产品最近一轮检查为缺货时，先提示再让用户自行决定是否继续跳转，
    避免「本站显示有货、跳过去才发现没货」的体感落差。"""
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>该套餐可能已缺货 - VPS 雷达</title></head>
<body style="font-family:system-ui,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f8fafc;">
<div style="max-width:420px;padding:32px;background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center;">
  <div style="font-size:40px;">📦</div>
  <h2 style="margin:12px 0 8px;color:#0f172a;">该套餐最近一轮检查为缺货</h2>
  <p style="color:#64748b;font-size:14px;line-height:1.7;">{escape(product.merchant.name)} · {escape(product.name)}<br>
  商家可能刚刚售罄或补货，实际库存以商家页面为准。</p>
  <a href="{escape(target_url, quote=True)}" style="display:inline-block;margin-top:12px;padding:10px 24px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;font-weight:600;">仍要前往商家查看</a>
  <div style="margin-top:14px;"><a href="/" style="color:#94a3b8;font-size:13px;">返回 VPS 雷达看看其他套餐</a></div>
</div>
</body>
</html>"""
    return HTMLResponse(html)


def build_purchase_url(product: Product, purchase_url: str | None = None) -> str:
    """有返利模板则套用（支持 {url} / {pid} 占位符），否则商家直链。

    针对搬瓦工 (BandwagonHost)：
    严格遵循官方推荐规范，将 cart.php? 替换为 aff.php?aff=83019&，
    完整保留 a=add&pid=...&billingcycle=... 等所选周期与配置参数。
    """
    purl = purchase_url or product.purchase_url
    if product.merchant.slug == "bandwagon":
        aff_id = "83019"
        if "cart.php?" in purl:
            return purl.replace("cart.php?", f"aff.php?aff={aff_id}&")
        pid = _extract_pid(purl) or _clean_pid(product.external_id)
        return f"https://bwh81.net/aff.php?aff={aff_id}&a=add&pid={pid}"

    template = product.merchant.aff_url_template
    if template and template.strip() and template.strip() != "{url}":
        try:
            pid = _extract_pid(purl) or _clean_pid(product.external_id)
            return template.format(url=quote(purl, safe=""), pid=pid)
        except (KeyError, IndexError):
            pass
    return purl


def _safe_http_url(url: str | None) -> str:
    """只允许 http(s) 跳转，并对插入 HTML 的值做转义。"""
    if not url:
        return "/"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "/"
    return url


def resolve_cycle_target(db: Session, product: Product, cycle: str | None) -> tuple[Product, str | None]:
    """在聚合组内按付款周期找到对应 SKU 与购买链接。"""
    members = group_members(db, product) or [product]
    want = (cycle or "").replace("-", "_")
    if not want:
        return product, product.purchase_url

    for member in members:
        member_cycle = (member.billing_cycle or "").replace("-", "_")
        if member_cycle == want:
            return member, member.purchase_url
        for opt in _get_product_price_options(member):
            if (opt.get("billing_cycle") or "").replace("-", "_") == want:
                return member, opt.get("purchase_url") or member.purchase_url
    return product, product.purchase_url


def _clean_pid(external_id: str | None) -> str:
    """从 external_id 提取纯数字 pid。

    各商家 external_id 格式不一（如 DMIT 的 `154_m` 月付变体、`dmit-183` 实时抓取），
    构造返利链接 `&pid=` 时需要纯数字，否则商家侧无法识别。
    """
    if not external_id:
        return ""
    m = re.search(r"(\d+)", external_id)
    return m.group(1) if m else external_id


def _extract_pid(purchase_url: str) -> str:
    """从商家直链提取纯数字 pid/id（如 cart.php?a=add&pid=154 或 ?cmd=cart&action=add&id=148）。"""
    if not purchase_url:
        return ""
    m = re.search(r"[?&](?:pid|id)=(\d+)", purchase_url)
    return m.group(1) if m else ""


@router.get("/go/{product_id}")
def go(
    product_id: int,
    request: Request,
    src: str = "site",
    cycle: str | None = None,
    db: Session = Depends(get_db),
):
    product = db.scalar(
        select(Product)
        .options(joinedload(Product.merchant))
        .where(Product.id == product_id)
    )
    if product is None or product.merchant is None or not product.merchant.enabled:
        raise HTTPException(status_code=404, detail="product not found")

    target_product, purchase_url = resolve_cycle_target(db, product, cycle)

    # 点击口径：缺货时用户会被插页拦下、并未真正到达商家，
    # src 追加 _oos 后缀便于后续分析剔除未成交点击（热度统计仍计入，代表关注意向）
    click_src = src if target_product.in_stock else f"{src[:26]}_oos"
    db.add(
        AffClick(
            product_id=target_product.id,
            src=click_src[:32],
            ip=request.client.host if request.client else None,
            ua=request.headers.get("user-agent", "")[:255],
        )
    )
    db.commit()

    want_cycle = (cycle or target_product.billing_cycle or "annually").replace("-", "_")

    # ZgoCloud 走自动提交 POST 表单，其余商家走 302 重定向
    if target_product.merchant.slug == "zgocloud":
        post_fields = {
            "action": "add",
            "id": target_product.external_id,
            "cycle": want_cycle,
        }
        if not target_product.in_stock:
            return _oos_interstitial(target_product, ZGOCLOUD_POST_URL)
        return _auto_post_page(ZGOCLOUD_POST_URL, post_fields)
    target = _safe_http_url(build_purchase_url(target_product, purchase_url))
    if not target_product.in_stock:
        return _oos_interstitial(target_product, target)
    return RedirectResponse(target, status_code=302)
