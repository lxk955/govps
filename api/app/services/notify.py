"""邮件通知（Resend）。低量级场景直接同步发送，无需队列。

渠道扩展：后续接入短信时，新增一个 channel 函数并在 dispatch 中分发即可，
notify_logs.channel 字段已预留 sms 枚举。
"""

from datetime import datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..models import EventType, NotifyEvent, NotifyLog, Product, User, Watchlist


def send_email(to: str, subject: str, html: str) -> tuple[bool, str | None]:
    if not settings.RESEND_API_KEY:
        return False, "RESEND_API_KEY not configured"
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.MAIL_FROM, "to": [to], "subject": subject, "html": html},
            timeout=15,
        )
    except httpx.HTTPError as e:
        return False, str(e)
    if resp.status_code in (200, 201):
        return True, None
    return False, f"resend {resp.status_code}: {resp.text[:200]}"


def render_event_email(event: NotifyEvent, p: Product) -> tuple[str, str]:
    specs = " / ".join(
        s
        for s in [
            f"{p.cpu_cores}C" if p.cpu_cores else "",
            f"{p.ram_gb}G" if p.ram_gb else "",
            f"{p.disk_gb}G SSD" if p.disk_gb else "",
            # -1 为无限流量标记，直接拼数字会显示成 "-1G 流量"
            ("不限流量" if p.bandwidth_gb < 0 else f"{p.bandwidth_gb}G 流量") if p.bandwidth_gb else "",
        ]
        if s
    )
    go_url = f"{settings.PUBLIC_API_URL}/go/{p.id}"
    cycle_cn = {
        "monthly": "月", "quarterly": "季", "semi-annually": "半年",
        "annually": "年", "biennially": "两年", "triennially": "三年",
        # 兼容部分爬虫产出的下划线写法（如 V.PS / DMIT 的 semi_annually）
        "semi_annually": "半年",
    }.get(p.billing_cycle, p.billing_cycle)

    merchant_name = escape(p.merchant.name or "")
    product_name = escape(p.name or "")
    loc = escape(p.location) if p.location else ""
    specs_safe = escape(specs)

    if event.type == EventType.RESTOCK:
        subject = f"【到货】{p.merchant.name} {p.name} · {p.currency} {p.price}/{cycle_cn}"
        headline = "你关注的产品补货了"
        src = "email_restock"
        detail = "检测到补货，库存可能随时变化，请以商家下单页实际库存为准"
    else:
        drop = ""
        if event.old_value and event.new_value:
            drop = f"{p.currency} {event.old_value} → {p.currency} {event.new_value}"
        subject = f"【降价】{p.merchant.name} {p.name} · {drop}"
        headline = "你关注的产品降价了"
        src = "email_drop"
        detail = f"价格变动：{escape(drop)}"

    html = f"""
    <h2>{headline}</h2>
    <p><b>{merchant_name} · {product_name}</b></p>
    <p>{specs_safe}{(' · ' + loc) if loc else ''}</p>
    <p>{detail}</p>
    <p>
      <a href="{go_url}?src={src}"
         style="display:inline-block;padding:10px 20px;background:#2563eb;color:#fff;
                border-radius:6px;text-decoration:none;">前往购买</a>
    </p>
    <p style="color:#888;font-size:12px">
      你因关注此产品而收到本邮件。部分链接为推广链接，价格不受影响。
    </p>
    """
    return subject, html


def _mails_sent_today(db: Session, user_id: int) -> int:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return db.scalar(
        select(func.count(NotifyLog.id)).where(
            NotifyLog.user_id == user_id,
            NotifyLog.channel == "email",
            NotifyLog.status == "sent",
            NotifyLog.sent_at >= today_start,
        )
    ) or 0


def dispatch_event(db: Session, event: NotifyEvent, product: Product) -> None:
    """把一个事件入队给所有满足条件的关注者（P7 异步化：只写 pending NotifyLog，
    不做任何网络发送——扫描主流程与邮件 RTT/失败完全解耦）。
    实际发送由 process_pending_emails 消费（后台 worker 或测试显式调用）。"""
    watchers = db.scalars(
        select(Watchlist).where(Watchlist.product_id == product.id)
    ).all()
    if not watchers:
        return

    drop_percent = 0.0
    if event.type == EventType.PRICE_DROP and event.old_value and event.new_value:
        old, new = float(event.old_value), float(event.new_value)
        if old > 0:
            drop_percent = (old - new) / old * 100

    for w in watchers:
        if event.type == EventType.RESTOCK and not w.notify_restock:
            continue
        if event.type == EventType.PRICE_DROP and (
            not w.notify_price_drop or drop_percent < float(w.min_drop_percent)
        ):
            continue

        user = db.get(User, w.user_id)
        if user is None:
            continue

        if _mails_sent_today(db, user.id) >= settings.DAILY_MAIL_CAP:
            db.add(NotifyLog(user_id=user.id, event_id=event.id, status="skipped",
                             error="daily cap reached"))
            continue

        db.add(NotifyLog(user_id=user.id, event_id=event.id,
                         status="pending", attempts=0))


def process_pending_emails(db: Session, batch_size: int = 50) -> dict:
    """消费 pending NotifyLog（P7 邮件异步 worker 的执行体）。

    多 Worker / 并发安全（Atomic Claiming）：
    - 认领：先通过 UPDATE notify_logs SET status='processing', attempts=attempts+1
      WHERE id = :id AND status = 'pending' 原子锁定行，仅认领成功的 Worker 才进入外呼；
    - 隔离：多 Worker / 多个后台线程 / 端点并发触发时，同一条记录绝不会被两个消费者同时拾取；
    - 重试：最多 EMAIL_MAX_ATTEMPTS 次；发信失败且未耗尽次数切回 pending 待下轮重试；
      耗尽后置 failed 终态并落日志；
    - 恢复：超时卡在 processing 状态的滞留任务自动重置为 pending。
    返回 {processed, sent, failed} 计数。"""
    max_attempts = settings.EMAIL_MAX_ATTEMPTS
    now = datetime.now(timezone.utc)

    # 1. 恢复超时 5 分钟仍为 processing 的异常滞留行（防 Worker 崩溃丢任务）
    stale_cutoff = now - timedelta(minutes=5)
    db.execute(
        update(NotifyLog)
        .where(NotifyLog.status == "processing", NotifyLog.sent_at < stale_cutoff)
        .values(status="pending")
    )
    db.commit()

    # 2. 查询待认领的主键列表
    pending_ids = db.scalars(
        select(NotifyLog.id)
        .where(
            NotifyLog.status == "pending",
            NotifyLog.attempts < max_attempts,
        )
        .limit(batch_size)
    ).all()

    processed = sent = failed = 0
    for log_id in pending_ids:
        # 3. 原子认领：CAS 更新 status='processing' 并累加 attempts
        claimed = db.execute(
            update(NotifyLog)
            .where(NotifyLog.id == log_id, NotifyLog.status == "pending")
            .values(status="processing", attempts=NotifyLog.attempts + 1, sent_at=now)
        ).rowcount
        db.commit()
        if claimed == 0:
            # 已被并发 Worker / 线程认领
            continue

        processed += 1
        log = db.get(NotifyLog, log_id)
        if log is None:
            continue

        event = db.get(NotifyEvent, log.event_id)
        user = db.get(User, log.user_id)
        product = db.get(Product, event.product_id) if event else None
        if event is None or user is None or product is None:
            log.status = "failed"
            log.error = "event/user/product missing"
            db.commit()
            failed += 1
            continue

        try:
            subject, html = render_event_email(event, product)
            ok, err = send_email(user.email, subject, html)
        except Exception as e:  # 发送器抛异常等同发送失败，不得中断整批
            ok, err = False, f"{type(e).__name__}: {e}"

        if ok:
            log.status = "sent"
            log.sent_at = datetime.now(timezone.utc)
            log.error = None
            sent += 1
        elif (log.attempts or 0) >= max_attempts:
            log.status = "failed"
            log.error = (err or "unknown")[:500]
            failed += 1
        else:
            # 切回 pending：下一轮 worker 重试
            log.status = "pending"
            log.error = (err or "")[:500]
        db.commit()

    return {"processed": processed, "sent": sent, "failed": failed}
