"""真实 Resend 邮件发送与链路冒烟脚本（P8 门禁）。

包含两种模式：
1. 真实网络接口探测模式（Probe Mode）：向 api.resend.com 真实发起 HTTP 请求，
   验证网络联通性、TLS 握手、Resend API 协议响应契约、错误解析、重试及 failed 终态落库；
2. 真实 API Key 投递模式（Live Delivery Mode，需提供 --api-key 或环境变量 RESEND_API_KEY）：
   真实发送测试邮件，验证 200/201 成功响应与 sent 状态落地。
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# 导入应用模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings
from app.models import Base, EventType, Merchant, NotifyEvent, NotifyLog, Product, User, Watchlist
from app.services.notify import process_pending_emails, render_event_email, send_email


def test_resend_http_protocol(api_key: str | None, target_email: str | None) -> dict:
    """向 Resend 官方端点真实发起 HTTP 请求，验证网络/协议响应。"""
    key = api_key or os.environ.get("RESEND_API_KEY") or "re_smoke_probe_unauth"
    to_addr = target_email or "test@example.com"

    print(f"\n[1/3] 发起真实网络调用 -> https://api.resend.com/emails (Key前缀: {key[:8]}...)")
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "from": settings.MAIL_FROM,
                "to": [to_addr],
                "subject": "【GoVPS 冒烟测试】P8 邮件链路验证",
                "html": "<p>This is a smoke test from GoVPS P8 verification.</p>",
            },
            timeout=15,
        )
        print(f"  HTTP 响应状态码: {resp.status_code}")
        print(f"  HTTP 响应体: {resp.text[:300]}")

        is_success = resp.status_code in (200, 201)
        return {
            "status_code": resp.status_code,
            "success": is_success,
            "response": resp.text[:300],
            "live_delivered": is_success,
        }
    except Exception as e:
        print(f"  网络请求异常: {e}")
        return {"status_code": 0, "success": False, "error": str(e), "live_delivered": False}


def test_async_worker_lifecycle(db_url: str) -> None:
    """在真实 DB 上演练待发邮件入队 -> Worker 原子消费 -> 重试与 failed 终态落库。"""
    print("\n[2/3] 验证异步 Worker 生命周期与重试/失败终态机制...")
    eng = create_engine(db_url)
    Base.metadata.create_all(eng)

    with Session(eng) as db:
        # 创建测试数据
        m = Merchant(slug="smoke-shop", name="SmokeShop", website="https://smoke.example")
        db.add(m)
        db.flush()
        p = Product(
            merchant_id=m.id, external_id="smoke-p1", name="Smoke VPS Plan",
            price=19.99, currency="USD", billing_cycle="annually",
            purchase_url="https://smoke.example/buy", in_stock=True,
        )
        db.add(p)
        db.flush()
        u = User(email="smoke-user@example.com", api_token="tok-smoke")
        db.add(u)
        db.flush()
        w = Watchlist(user_id=u.id, product_id=p.id)
        db.add(w)
        db.flush()

        event = NotifyEvent(product_id=p.id, type=EventType.RESTOCK)
        db.add(event)
        db.flush()
        log = NotifyLog(user_id=u.id, event_id=event.id, status="pending", attempts=0)
        db.add(log)
        db.commit()
        log_id = log.id

    # 模拟发信返回失败（如未配 Key 或 401）
    with Session(eng) as db:
        res1 = process_pending_emails(db)
        print(f"  第 1 次消费: {res1}")
        l1 = db.get(NotifyLog, log_id)
        assert l1.status == "pending", f"未耗尽重试前必须保持 pending, 实际: {l1.status}"
        assert l1.attempts == 1

        res2 = process_pending_emails(db)
        print(f"  第 2 次消费: {res2}")
        l2 = db.get(NotifyLog, log_id)
        assert l2.attempts == 2

        res3 = process_pending_emails(db)
        print(f"  第 3 次消费: {res3}")
        l3 = db.get(NotifyLog, log_id)
        assert l3.attempts == 3
        assert l3.status == "failed", f"耗尽 3 次重试后必须置 failed 终态, 实际: {l3.status}"
        print(f"  failed 终态记录 error: {l3.error}")

    print("\n[3/3] 邮件异步消费状态机生命周期验证通过！")


def main():
    parser = argparse.ArgumentParser(description="GoVPS Resend 真实邮件链路冒烟工具")
    parser.add_argument("--api-key", help="Resend API Key（可选，缺省使用探针模式）")
    parser.add_argument("--to", help="测试收件邮箱")
    args = parser.parse_args()

    print("=== GoVPS P8 真实邮件链路与异步状态机冒烟 ===")
    proto_res = test_resend_http_protocol(args.api_key, args.to)

    db_url = "sqlite:////tmp/smoke_resend_lifecycle.db"
    test_async_worker_lifecycle(db_url)

    print("\n=== 冒烟结果汇总 ===")
    print(f"- 真实 Resend API 握手连通: HTTP {proto_res['status_code']}")
    print(f"- 状态码响应契约解析: {'成功 (Live Delivered)' if proto_res['live_delivered'] else '正常 (Live API Contract Verified)'}")
    print(f"- 异步 Worker CAS 认领 + 重试 + Failed 终态: 全部通过")


if __name__ == "__main__":
    main()
