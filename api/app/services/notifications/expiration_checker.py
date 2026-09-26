"""VPS 到期自动化巡检、提醒阶段判定与邮件模板渲染。"""

import base64
import hashlib
import hmac
import json
import logging
import math
import time
from datetime import datetime, timezone
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...models import User, UserNode
from .dispatcher import dispatcher

logger = logging.getLogger(__name__)


def _get_signing_key(node_token: str = "") -> bytes:
    server_secret = (settings.TASK_TOKEN or "govps-secret-task-token").strip()
    # 结合服务器 TASK_TOKEN 与节点专属的 64 位私密 node.token，彻底防止默认 TASK_TOKEN (如 change-me) 被外部伪造签名
    combined = f"{server_secret}:{node_token}"
    return hashlib.sha256(combined.encode("utf-8")).digest()


def generate_renewal_token(node: UserNode, valid_days: int = 30) -> str:
    """生成 30 天有效的免密安全续费 Token，绑定 node.id 与 node.expires_at。"""
    from ...models import to_iso_utc

    exp_ts = int(time.time()) + valid_days * 86400
    node_exp_str = to_iso_utc(node.expires_at) or ""
    payload = {
        "nid": node.id,
        "uid": node.user_id,
        "exp": exp_ts,
        "nexp": node_exp_str,
        "act": "renew",
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")

    key = _get_signing_key(node.token)
    sig = hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def verify_renewal_token(token: str, db: Session | None = None) -> tuple[dict | None, UserNode | None]:
    """验证续费 Token。
    
    校验签名与过期时间。若提供 db，则还会加载 node 并用 node.token 强校验签名防伪造。
    若合法返回 (payload, node)，否则返回 (None, None)。
    """
    if not token or "." not in token:
        return None, None
    try:
        parts = token.strip().split(".")
        if len(parts) != 2:
            return None, None
        payload_b64, sig_b64 = parts[0], parts[1]

        pad_p = "=" * ((4 - len(payload_b64) % 4) % 4)
        pad_s = "=" * ((4 - len(sig_b64) % 4) % 4)

        payload_bytes = base64.urlsafe_b64decode(payload_b64 + pad_p)
        payload = json.loads(payload_bytes.decode("utf-8"))

        if payload.get("act") != "renew":
            return None, None
        if payload.get("exp", 0) < int(time.time()):
            return None, None

        node = None
        node_token = ""
        if db is not None:
            node_id = payload.get("nid")
            node = db.get(UserNode, node_id)
            if not node:
                return None, None
            node_token = node.token or ""

        key = _get_signing_key(node_token)
        expected_sig = hmac.new(key, payload_b64.encode("ascii"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64 + pad_s)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None, None

        return payload, node
    except Exception:
        return None, None

# 国家简码到常见 Emoji 国旗映射
COUNTRY_FLAGS: dict[str, str] = {
    "hk": "🇭🇰", "us": "🇺🇸", "jp": "🇯🇵", "sg": "🇸🇬", "de": "🇩🇪",
    "gb": "🇬🇧", "kr": "🇰🇷", "tw": "🇹🇼", "ca": "🇨🇦", "au": "🇦🇺",
    "fr": "🇫🇷", "nl": "🇳🇱", "ru": "🇷🇺", "cn": "🇨🇳", "my": "🇲🇾",
}

CYCLE_NAMES: dict[str, str] = {
    "monthly": "按月付",
    "quarterly": "按季付",
    "semi-annually": "按半年付",
    "semi_annually": "按半年付",
    "annually": "按年付",
    "biennially": "按两年付",
    "triennially": "按三年付",
}


def render_expiration_email(
    node: UserNode,
    days_left: int,
    stage: int | None = None,
    is_test: bool = False,
) -> tuple[str, str]:
    """渲染 VPS 到期提醒或测试邮件的标题和 HTML 内容。"""
    node_name = escape(node.name or "未命名节点")
    flag = COUNTRY_FLAGS.get((node.country or "").lower(), "🌐")
    country_code = (node.country or "HK").upper()
    cycle_text = CYCLE_NAMES.get(node.billing_cycle or "monthly", node.billing_cycle or "月付")
    price_text = f"{node.currency or 'USD'} {float(node.price):.2f}" if node.price is not None else "未设置"
    traffic_text = f"{node.traffic_limit_gb:.0f} GB / 月" if node.traffic_limit_gb else "无限制"

    exp_date_str = "未知"
    if node.expires_at:
        exp = node.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        exp_date_str = exp.strftime("%Y-%m-%d %H:%M UTC")

    monitor_url = f"{settings.PUBLIC_API_URL.rstrip('/')}/monitor"
    if is_test:
        renewal_token = ""
        renew_url = ""
    else:
        renewal_token = (
            generate_renewal_token(node)
            if (node and getattr(node, "id", None) and getattr(node, "token", None))
            else ""
        )
        renew_url = (
            f"{settings.PUBLIC_API_URL.rstrip('/')}/monitor/renew?token={renewal_token}"
            if renewal_token
            else monitor_url
        )

    if is_test:
        subject = f"【测试】GoVPS 探针 · VPS 到期提醒连通性测试"
        badge_text = "测试邮件 · 连通性正常"
        badge_bg = "#3b82f6"
        headline = "🎉 探针到期提醒通道测试成功"
        subhead = f"这是一封测试邮件，用以验证 Resend 邮件服务与 GoVPS 到期监控提醒机制的连通性。"
    elif days_left <= 0:
        subject = f"【紧急到期】您的 VPS「{node.name}」今日到期，请尽快续费！"
        badge_text = "今日到期 · 极高风险"
        badge_bg = "#ef4444"
        headline = f"⚠️ 您的 VPS 节点已到达设定到期日"
        subhead = f"节点「{node_name}」将于今日到期，如需继续使用请尽快前往商家控制台续费，避免数据丢失或实例被回收。"
    elif days_left <= 3:
        subject = f"【加急到期】您的 VPS「{node.name}」仅剩 {days_left} 天到期（{exp_date_str}）"
        badge_text = f"仅剩 {days_left} 天到期"
        badge_bg = "#f97316"
        headline = f"⏳ 您的 VPS 节点即将于 {days_left} 天后到期"
        subhead = f"节点「{node_name}」已进入加急续费期，请注意关注商家账单与续费状态。"
    else:
        subject = f"【到期提醒】您的 VPS「{node.name}」将在 {days_left} 天后到期（{exp_date_str}）"
        badge_text = f"剩余 {days_left} 天到期"
        badge_bg = "#eab308"
        headline = f"📅 您的 VPS 节点将在 {days_left} 天后到期"
        subhead = f"检测到节点「{node_name}」设置了到期日，根据您的提醒配置特向您发送通知。"

    if is_test:
        action_buttons_html = f"""
          <div style="text-align: center; margin: 28px 0 16px 0;">
            <a href="{monitor_url}"
               style="display: inline-block; padding: 12px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 14px; border-radius: 10px; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);">
              前往探针面板管理
            </a>
          </div>
          <p style="text-align: center; font-size: 12px; color: #94a3b8; margin: 0;">
            这是一封连通性测试邮件，未附带节点续费操作链接，不会修改任何节点状态。
          </p>
        """
    else:
        action_buttons_html = f"""
          <div style="text-align: center; margin: 28px 0 16px 0;">
            <a href="{renew_url}"
               style="display: inline-block; padding: 13px 36px; background-color: #16a34a; color: #ffffff; text-decoration: none; font-weight: 700; font-size: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(22, 163, 74, 0.25);">
              ✅ 我已续费 / 静音本期提醒
            </a>
            <div style="margin-top: 14px;">
              <a href="{monitor_url}"
                 style="font-size: 13px; color: #64748b; text-decoration: underline;">
                前往探针面板管理 &rarr;
              </a>
            </div>
          </div>
          <p style="text-align: center; font-size: 12px; color: #94a3b8; margin: 0;">
            点击「我已续费」将停止本到期周期的后续催促邮件，并可在打开的页面中设置下次续费到期日。
          </p>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>{subject}</title>
    </head>
    <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b;">
      <div style="max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
        <!-- 头部 -->
        <div style="padding: 24px 28px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); color: #ffffff;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <span style="font-size: 13px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; color: #94a3b8;">GoVPS · 探针监控</span>
            <span style="display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 700; color: #ffffff; background-color: {badge_bg};">
              {badge_text}
            </span>
          </div>
          <h1 style="margin: 0; font-size: 20px; font-weight: 700; line-height: 1.4; color: #ffffff;">{headline}</h1>
          <p style="margin: 8px 0 0 0; font-size: 13px; color: #cbd5e1; line-height: 1.5;">{subhead}</p>
        </div>

        <!-- 资产卡片 -->
        <div style="padding: 24px 28px;">
          <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px 20px; margin-bottom: 20px;">
            <div style="margin-bottom: 14px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 12px;">
              <span style="font-size: 18px; margin-right: 6px;">{flag}</span>
              <strong style="font-size: 16px; color: #0f172a;">{node_name}</strong>
              <span style="font-size: 12px; color: #64748b; margin-left: 8px;">({country_code} · {escape(node.group_name or '默认组')})</span>
            </div>

            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
              <tr>
                <td style="padding: 6px 0; color: #64748b; width: 35%;">到期时间:</td>
                <td style="padding: 6px 0; color: #0f172a; font-weight: 600; font-family: monospace;">{exp_date_str}</td>
              </tr>
              <tr>
                <td style="padding: 6px 0; color: #64748b;">续费价格与周期:</td>
                <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{price_text} / {cycle_text}</td>
              </tr>
              <tr>
                <td style="padding: 6px 0; color: #64748b;">流量额度:</td>
                <td style="padding: 6px 0; color: #0f172a;">{traffic_text}</td>
              </tr>
              <tr>
                <td style="padding: 6px 0; color: #64748b;">操作系统:</td>
                <td style="padding: 6px 0; color: #0f172a;">{escape(node.os_type or 'Linux')}</td>
              </tr>
            </table>
          </div>

          <!-- 操作按钮 -->
          {action_buttons_html}
        </div>

        <!-- 页脚 -->
        <div style="padding: 16px 28px; background-color: #f1f5f9; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
          此邮件由 GoVPS (<a href="{settings.PUBLIC_API_URL}" style="color: #64748b; text-decoration: underline;">govps.xyz</a>) 探针自动巡检系统发送。<br/>
          您可以在探针面板的「设置 → 到期提醒」中随时调整提醒阶段天数或关闭提醒。
        </div>
      </div>
    </body>
    </html>
    """
    return subject, html


def check_expiring_nodes(db: Session) -> dict:
    """巡检所有设置了到期时间的 VPS 节点，执行多阶段去重提醒并记录状态。"""
    now = datetime.now(timezone.utc)
    # 查询所有非演示、且设置了到期时间的节点
    stmt = (
        select(UserNode)
        .where(UserNode.expires_at.is_not(None), UserNode.is_demo == False)  # noqa: E712
    )
    nodes = db.scalars(stmt).all()

    checked_count = 0
    notified_count = 0
    errors = []

    for node in nodes:
        checked_count += 1
        user = node.user
        if not user or not user.email:
            continue

        # 1. 检查是否开启提醒：单节点优先，否则继承用户全局设置
        if node.expire_muted:
            continue
        if node.expire_notify_enabled is False:
            continue
        if node.expire_notify_enabled is None and not user.monitor_expire_notify_enabled:
            continue

        # 2. 获取生效的提醒阶段列表（降序整数列表）
        raw_stages = node.expire_notify_stages
        if raw_stages is None:
            raw_stages = user.monitor_expire_stages or [15, 7, 3, 1]

        try:
            effective_stages = sorted(
                [int(s) for s in raw_stages if int(s) >= 0], reverse=True
            )
        except Exception:
            effective_stages = [15, 7, 3, 1]

        if not effective_stages:
            continue

        # 3. 计算剩余天数
        exp = node.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        # 到期时间已过超过 1 天，不再巡检发送（避免过期老机器永久重复）
        diff_seconds = (exp - now).total_seconds()
        if diff_seconds < -86400:
            continue

        days_left = max(0, int(math.ceil(diff_seconds / 86400.0)))
        notified_set = set(node.notified_expire_stages or [])

        # 4. 找到满足 days_left <= stage 且 stage 尚未被通知的阶段
        # 寻找匹配的最小阶段（最紧急）
        candidate_stages = [s for s in effective_stages if days_left <= s and s not in notified_set]
        if not candidate_stages:
            continue

        trigger_stage = min(candidate_stages)

        # 5. 渲染并派发提醒
        subject, html = render_expiration_email(node, days_left, stage=trigger_stage)
        res = dispatcher.dispatch(user, subject, html, channels=["email"])
        ok, err = res.get("email", (False, "未知错误"))

        if ok:
            notified_count += 1
            # 将该阶段及所有大于该阶段的 stage 记为已通知，防止时间跨度跳跃漏记
            new_notified = notified_set.union(s for s in effective_stages if s >= trigger_stage)
            node.notified_expire_stages = sorted(list(new_notified), reverse=True)
            db.commit()
            logger.info(
                f"[ExpirationCheck] Notified user {user.email} for node {node.name} (days_left={days_left}, stage={trigger_stage})"
            )
        else:
            errors.append(f"Node {node.id} ({node.name}): {err}")
            logger.warning(
                f"[ExpirationCheck] Failed to notify {user.email} for node {node.id}: {err}"
            )

    return {
        "checked": checked_count,
        "notified": notified_count,
        "errors": errors,
    }


def send_test_expiration_email(db: Session, user: User) -> tuple[bool, str | None]:
    """向目标用户发送一封用于验证连通性的测试到期提醒邮件（纯虚拟样例，绝不绑定真实节点操作链接）。"""
    sample_node = UserNode(
        id=None,
        token="",
        user_id=user.id,
        name="示例 VPS (连通性测试)",
        country="hk",
        group_name="主力演示",
        billing_cycle="monthly",
        price=29.99,
        currency="USD",
        traffic_limit_gb=1024,
        os_type="Debian 12",
        expires_at=datetime.now(timezone.utc),
    )

    subject, html = render_expiration_email(
        node=sample_node,
        days_left=7,
        stage=7,
        is_test=True,
    )

    results = dispatcher.dispatch(user, subject, html, channels=["email"])
    ok, err = results.get("email", (False, "邮件渠道未响应"))
    return ok, err
