"""P7 分级调度与故障隔离测试（refactor-plan §2 #4、§3 P7 验收项）。

- 分级调度：非 force 时仅抓取「已到期」商家（now - last_success_at ≥ 间隔），
  间隔兜底链为 商家列 crawl_interval_minutes → adapter 默认值 → 全局配置；
- 故障隔离：单个商家 fetch 抛错不影响其他商家的抓取入库（AGENTS.md Crawlers）。

套件零外部网络：make_client 替换为不发出任何请求的空客户端；
商家数据全部由 FakeCrawler 直接返回 RawProduct。
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.models import Merchant, Product
from app.crawler.base import RawProduct
from app.services.scan import effective_interval_minutes, ensure_merchants, run_scan


def _get_merchant(db, slug: str) -> Merchant:
    return db.scalar(select(Merchant).where(Merchant.slug == slug))


class _NullClient:
    """替代 httpx.Client 的上下文管理器：任何误发请求都会在此显式失败。"""

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


def _raw(slug_pid: str = "p1") -> RawProduct:
    return RawProduct(
        external_id=slug_pid,
        name=f"Plan {slug_pid}",
        price=Decimal("5.00"),
        currency="USD",
        billing_cycle="monthly",
        purchase_url=f"https://buy.example/{slug_pid}",
        in_stock=True,
    )


def _fake_crawler(slug: str, fetch, interval: int | None = None):
    c = SimpleNamespace(
        slug=slug,
        name=slug.title(),
        website=f"https://{slug}.example",
        aff_url_template=None,
        default_interval_minutes=interval,
        fetch=fetch,
    )
    return c


@pytest.fixture(autouse=True)
def _no_http(monkeypatch):
    monkeypatch.setattr("app.services.scan.make_client", lambda timeout: _NullClient())


@pytest.fixture
def patched_crawlers(monkeypatch):
    """替换扫描注册表；返回可读写的列表供用例注入 FakeCrawler。"""
    crawlers: list = []
    monkeypatch.setattr("app.services.scan.CRAWLERS", crawlers)
    return crawlers


# ── 间隔兜底链 ─────────────────────────────────────────────────


def test_interval_fallback_chain(db, patched_crawlers):
    adapter = _fake_crawler("chainshop", lambda client: [], interval=45)
    patched_crawlers.append(adapter)
    ensure_merchants(db)

    m = _get_merchant(db, "chainshop")
    # ensure_merchants 把 adapter 默认值填充进空列（运营改库后不被覆盖）
    assert m.crawl_interval_minutes == 45

    # 商家列优先
    m.crawl_interval_minutes = 90
    assert effective_interval_minutes(m, adapter) == 90
    # 列清空 → adapter 默认值
    m.crawl_interval_minutes = None
    assert effective_interval_minutes(m, adapter) == 45
    # 双缺 → 全局兜底（getattr 缺属性也走 settings）
    bare = _fake_crawler("bargain", lambda client: [])
    assert effective_interval_minutes(m, bare) == settings.CRAWL_INTERVAL_MINUTES


# ── 到期判断：未到期跳过 / force 强制 / 到期照抓 ────────────────


def _seed_merchant(db, slug: str, *, minutes_ago: int | None, interval: int | None) -> Merchant:
    ensure_merchants(db)
    m = _get_merchant(db, slug)
    if interval is not None:
        m.crawl_interval_minutes = interval
    if minutes_ago is not None:
        m.last_success_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    db.commit()
    return m


def test_not_due_merchant_is_skipped_without_fetch(db, patched_crawlers):
    calls: list[str] = []

    def fetch(client):
        calls.append("fetched")
        return [_raw()]

    patched_crawlers.append(_fake_crawler("freshshop", fetch))
    _seed_merchant(db, "freshshop", minutes_ago=2, interval=30)

    result = run_scan(db)
    assert calls == []                                   # 未到期绝不发请求
    assert "not due" in result["summary"]["freshshop"]
    assert "due in" in result["summary"]["freshshop"]    # 提示剩余到期时间
    assert _get_merchant(db, "freshshop").last_error is None


def test_force_bypasses_due_check(db, patched_crawlers):
    calls: list[str] = []

    def fetch(client):
        calls.append("fetched")
        return [_raw()]

    patched_crawlers.append(_fake_crawler("freshshop2", fetch))
    _seed_merchant(db, "freshshop2", minutes_ago=2, interval=30)

    run_scan(db, force=True)
    assert calls == ["fetched"]                          # 手动补扫忽略到期判断


def test_due_merchant_is_fetched_and_marks_success(db, patched_crawlers):
    calls: list[str] = []

    def fetch(client):
        calls.append("fetched")
        return [_raw("due-1")]

    patched_crawlers.append(_fake_crawler("staleshop", fetch))
    _seed_merchant(db, "staleshop", minutes_ago=120, interval=30)

    run_scan(db)
    assert calls == ["fetched"]
    m = _get_merchant(db, "staleshop")
    p = db.scalar(select(Product).where(Product.external_id == "due-1"))
    assert p is not None and p.in_stock is True
    assert m.last_success_at is not None and m.last_error is None
    # 从未成功抓取的商家视为已到期：last_success_at 为 NULL 也必须被抓取
    fresh = _get_merchant(db, "staleshop")
    fresh.last_success_at = None
    db.commit()
    calls.clear()
    run_scan(db)
    assert calls == ["fetched"]


def test_adapter_default_interval_applies_when_column_null(db, patched_crawlers):
    calls: list[str] = []

    def fetch(client):
        calls.append("fetched")
        return [_raw()]

    # 先建行再挂 adapter 默认值：模拟旧库中列仍为 NULL 的升级场景
    patched_crawlers.append(_fake_crawler("legacyshop", fetch))
    ensure_merchants(db)
    m = _get_merchant(db, "legacyshop")
    m.crawl_interval_minutes = None
    m.last_success_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()

    patched_crawlers[0].default_interval_minutes = 20
    run_scan(db)
    assert calls == []                                   # 5min < 20min，按 adapter 默认值跳过


# ── 单商家故障隔离 ──────────────────────────────────────────────


def test_single_merchant_failure_does_not_block_others(db, patched_crawlers):
    def broken(client):
        raise RuntimeError("merchant site exploded")

    def healthy(client):
        return [
            _raw("ok-1"),
            RawProduct(external_id="ok-2", name="Plan ok-2", price=Decimal("9.99"),
                       currency="USD", billing_cycle="monthly",
                       purchase_url="https://buy.example/ok-2", in_stock=False),
            RawProduct(external_id="ok-3", name="Plan ok-3", price=Decimal("19.99"),
                       currency="USD", billing_cycle="monthly",
                       purchase_url="https://buy.example/ok-3", in_stock=True),
        ]

    bad = _fake_crawler("badshop", broken)
    good = _fake_crawler("goodshop", healthy)
    patched_crawlers.extend([bad, good])

    result = run_scan(db)

    assert result["ok"] is True                          # 主流程完成，不被单商家失败打断
    assert result["summary"]["badshop"].startswith("error:")
    assert "exploded" in result["summary"]["badshop"]
    m_bad = _get_merchant(db, "badshop")
    assert "exploded" in (m_bad.last_error or "")        # 失败落库可观察
    assert m_bad.last_success_at is None                 # 失败不推进成功时间（到期判断不受污染）

    # 另一商家完整走完 抓取→入库→快照 流程（3 款过完整性门槛，走正常 summary 分支）
    assert "3 products" in result["summary"]["goodshop"]
    m_good = _get_merchant(db, "goodshop")
    assert m_good.last_success_at is not None and m_good.last_error is None
    ids = {
        pid
        for (pid,) in db.execute(
            select(Product.external_id).where(Product.merchant_id == m_good.id)
        )
    }
    assert ids == {"ok-1", "ok-2", "ok-3"}
