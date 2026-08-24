"""P7 邮件异步化测试（故障隔离证据）。套件零外部网络：
run_scan 的 HTTP 客户端被替换为立即失败的 MockTransport。

断言核心契约：
- 扫描主流程不因邮件发送器缓慢/抛错而失败或阻塞（发送器在扫描期根本不被调用）；
- pending NotifyLog 由 worker 执行体消费；失败可重试、状态可记录、成功后不重发。
发信统一 monkeypatch app.services.notify.send_email（真实 Resend 链路未验证，见 §10）。
"""

from decimal import Decimal

import httpx
import pytest

from app.models import Merchant, NotifyEvent, NotifyLog, Product, User, Watchlist
from app.services.scan import run_scan


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """所有用例的扫描期 HTTP 一律立即失败：零外网依赖 + 快速返回。"""
    def failing_client(*a, **k):
        return httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(500)),
            timeout=2.0,
        )

    monkeypatch.setattr("app.services.scan.make_client", failing_client)


@pytest.fixture
def watcher_and_product(db):
    m = Merchant(slug="mailshop", name="MailShop", website="https://m.example")
    db.add(m)
    db.flush()
    p = Product(
        merchant_id=m.id, external_id="mp-1", name="Notify Plan",
        price=Decimal("10"), currency="USD", billing_cycle="annually",
        purchase_url="https://m.example/buy", in_stock=True,
    )
    db.add(p)
    db.flush()
    u = User(email="watcher@example.com", api_token="tok-mail")
    db.add(u)
    db.flush()
    db.add(Watchlist(user_id=u.id, product_id=p.id))
    db.commit()
    return p, u


def _enqueue_restock(db, product_id: int) -> int:
    """构造补货事件并入队（等价于扫描期 upsert 检出补货后的行为）。"""
    event = NotifyEvent(product_id=product_id, type="RESTOCK",
                        old_value="out_of_stock", new_value="in_stock")
    db.add(event)
    db.flush()
    from app.models import Product as P

    from app.services.notify import dispatch_event

    dispatch_event(db, event, db.get(P, product_id))
    db.commit()
    return db.query(NotifyLog).filter_by(status="pending").count()


def test_scan_completes_without_calling_sender_when_it_would_hang(
    client, db, monkeypatch
):
    """故障隔离①：发送器「会挂起并爆炸」时，扫描主流程正常完成且不调用它。"""
    calls = []

    def exploding_sender(*a, **k):  # pragma: no cover - 若被调用即失败
        calls.append(1)
        raise RuntimeError("sender must not be called synchronously during scan")

    monkeypatch.setattr("app.services.notify.send_email", exploding_sender)

    summary = run_scan(db)
    assert summary["ok"] is True   # 所有商家源 500 失败，但主流程完成且互不阻塞
    assert calls == []             # 扫描期完全未触碰发送器


def test_worker_sends_pending_marks_sent(client, db, monkeypatch, watcher_and_product):
    p, _u = watcher_and_product
    assert _enqueue_restock(db, p.id) == 1

    from app.services.notify import process_pending_emails

    monkeypatch.setattr("app.services.notify.send_email", lambda *a, **k: (True, None))
    result = process_pending_emails(db)
    assert result == {"processed": 1, "sent": 1, "failed": 0}
    log = db.query(NotifyLog).one()
    assert log.status == "sent"
    assert log.attempts == 1

    # 幂等：已 sent 的不再被处理、不重复发送
    again = process_pending_emails(db)
    assert again["processed"] == 0
    assert db.query(NotifyLog).filter_by(status="sent").count() == 1


def test_retry_then_permanent_failure_is_observable(client, db, monkeypatch, watcher_and_product):
    p, _u = watcher_and_product
    _enqueue_restock(db, p.id)

    from app.services.notify import process_pending_emails

    # 前 2 次：SMTP 超时（模拟 httpx.TimeoutException 冒泡）
    def timeout_sender(*a, **k):
        raise TimeoutError("smtp read timed out")

    monkeypatch.setattr("app.services.notify.send_email", timeout_sender)
    r1 = process_pending_emails(db)
    r2 = process_pending_emails(db)
    assert (r1["failed"], r2["failed"]) == (0, 0)     # 未耗尽前保持 pending 可重试
    log = db.query(NotifyLog).one()
    assert log.status == "pending"
    assert log.attempts == 2
    assert "timed out" in (log.error or "")

    # 第 3 次（最后一次）：仍失败 → 终态 failed，错误可观察
    r3 = process_pending_emails(db)
    assert r3["failed"] == 1
    assert log.status == "failed"
    assert "timed out" in (log.error or "")

    # 终态后不再重试（不会反复打扰收件人）
    monkeypatch.setattr("app.services.notify.send_email", lambda *a, **k: (True, None))
    assert process_pending_emails(db)["processed"] == 0
    assert db.query(NotifyLog).count() == 1


def test_retry_recovers_on_later_attempt(client, db, monkeypatch, watcher_and_product):
    """失败→恢复路径：第 1 次超时，第 2 次成功 → sent。"""
    p, _u = watcher_and_product
    _enqueue_restock(db, p.id)

    from app.services.notify import process_pending_emails

    state = {"n": 0}

    def flaky(*a, **k):
        state["n"] += 1
        if state["n"] == 1:
            raise TimeoutError("transient")
        return True, None

    monkeypatch.setattr("app.services.notify.send_email", flaky)
    process_pending_emails(db)
    assert db.query(NotifyLog).one().status == "pending"
    process_pending_emails(db)
    assert db.query(NotifyLog).one().status == "sent"


def test_scan_time_budget_not_consuming_mail_rtt(client, db, monkeypatch, watcher_and_product):
    """验收项「扫描耗时不再受邮件 RTT 影响」的量化证据：
    待发邮件的发送器每次阻塞 1.5s 时——
    - run_scan 耗时保持在亚秒级（旧同步实现此处会被 +1.5s/封 阻塞）；
    - 延迟只由 worker 阶段吸收。
    边界取值宽松，避免 CI 负载抖动造成误报。"""
    import time

    from app.services.notify import process_pending_emails

    p, _u = watcher_and_product
    _enqueue_restock(db, p.id)

    def slow_sender(*a, **k):
        time.sleep(1.5)
        return True, None

    monkeypatch.setattr("app.services.notify.send_email", slow_sender)

    t0 = time.perf_counter()
    summary = run_scan(db)
    scan_seconds = time.perf_counter() - t0
    assert summary["ok"] is True
    assert scan_seconds < 1.0                # 扫描期不触碰发送器，RTT 不进扫描预算

    t1 = time.perf_counter()
    result = process_pending_emails(db)
    worker_seconds = time.perf_counter() - t1
    assert result == {"processed": 1, "sent": 1, "failed": 0}
    assert worker_seconds >= 1.4             # RTT 由 worker 吸收且只发生在这里


def test_daily_cap_still_enforced_at_enqueue(client, db, monkeypatch, watcher_and_product):
    """每日上限逻辑保持在入队侧（异步化不改变配额语义）。"""
    from datetime import datetime, timezone

    from app.config import settings

    p, u = watcher_and_product
    event = NotifyEvent(product_id=p.id, type="RESTOCK", old_value="oos", new_value="in")
    db.add(event)
    db.flush()
    for i in range(settings.DAILY_MAIL_CAP):
        db.add(NotifyLog(user_id=u.id, event_id=event.id, channel="email",
                         status="sent", sent_at=datetime.now(timezone.utc)))
    db.commit()

    monkeypatch.setattr("app.services.notify.send_email", lambda *a, **k: (True, None))
    _enqueue_restock(db, p.id)
    statuses = [l.status for l in db.query(NotifyLog).filter(NotifyLog.status != "sent").all()]
    assert statuses == ["skipped"]                    # 入队即被日限额跳过


# ── /api/tasks/process-emails：进程内 worker 的 cron 兜底入口 ──────────


def test_process_emails_endpoint_requires_token(client, db):
    r = client.post("/api/tasks/process-emails")
    assert r.status_code == 403
    r = client.post("/api/tasks/process-emails", headers={"X-Task-Token": "wrong"})
    assert r.status_code == 403


def test_process_emails_endpoint_drains_pending(
    client, db, monkeypatch, watcher_and_product
):
    p, _u = watcher_and_product
    _enqueue_restock(db, p.id)

    monkeypatch.setattr("app.services.notify.send_email", lambda *a, **k: (True, None))
    r = client.post(
        "/api/tasks/process-emails", headers={"X-Task-Token": "test-task-token"}
    )
    assert r.status_code == 200
    assert r.json() == {"processed": 1, "sent": 1, "failed": 0}

    # 幂等：再次调用无 pending 可消费，不重复发送
    r2 = client.post(
        "/api/tasks/process-emails", headers={"X-Task-Token": "test-task-token"}
    )
    assert r2.json() == {"processed": 0, "sent": 0, "failed": 0}
    assert db.query(NotifyLog).filter_by(status="sent").count() == 1


def test_concurrent_workers_atomic_claiming_no_duplicate_sends(db, monkeypatch):
    """多 Worker / 并发消费防重发断言：
    多个 Worker 线程同时并发拾取 pending 行时，CAS 原子认领保证每封邮件被且仅被发送一次。"""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from app.database import SessionLocal
    from app.services.notify import process_pending_emails

    m = Merchant(slug="cshop", name="CShop", website="https://c.example")
    db.add(m)
    db.flush()

    # 创建 6 个待发送事件与关注记录
    for i in range(6):
        p = Product(
            merchant_id=m.id, external_id=f"cp-{i}", name=f"Plan {i}",
            price=Decimal("10"), currency="USD", billing_cycle="annually",
            purchase_url="https://c.example/buy", in_stock=True,
        )
        db.add(p)
        db.flush()
        u = User(email=f"watcher{i}@example.com", api_token=f"tok-c-{i}")
        db.add(u)
        db.flush()
        db.add(Watchlist(user_id=u.id, product_id=p.id))
        db.flush()
        _enqueue_restock(db, p.id)

    assert db.query(NotifyLog).filter_by(status="pending").count() == 6

    send_lock = threading.Lock()
    sent_targets: list[str] = []

    def mock_send(to: str, subject: str, html: str):
        with send_lock:
            sent_targets.append(to)
        return True, None

    monkeypatch.setattr("app.services.notify.send_email", mock_send)

    def worker_run():
        with SessionLocal() as worker_db:
            return process_pending_emails(worker_db)

    # 4 个 Worker 线程同时并发消费
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(worker_run) for _ in range(4)]
        results = [f.result() for f in futures]

    total_sent = sum(r["sent"] for r in results)
    assert total_sent == 6
    assert len(sent_targets) == 6, "每封邮件必须严格只被发送一次，严禁并发重复发信"
    assert len(set(sent_targets)) == 6, "所有收件人必须唯一，无任何重复认领"
    assert db.query(NotifyLog).filter_by(status="sent").count() == 6

