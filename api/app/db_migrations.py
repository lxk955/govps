"""版本化迁移入口（P7）：Alembic 正式接管 schema 演进（refactor-plan §2 #8 / §4）。

startup 与运维命令共用本模块，策略：

- 空库：直接 ``alembic upgrade head`` 从零构建到最新；
- 存量旧库（有业务表、无 alembic_version，即 Alembic 引入前的部署）：
  按「哨兵」逐级判定结构已到达的版本 → ``stamp`` 该版本 → 继续增量升级。
  哨兵取每个迁移引入的首个对象（列/表），单调递增、只前不退，
  因此对「已由旧代码补过部分列」的中间形态同样给出正确落点；
- 已纳管库：常规 ``upgrade head``。

并发说明：Render 部署为单实例单 worker，startup 迁移不存在竞争；
未来多副本部署时迁移应移入发布流程的独立步骤（先迁后滚）。
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy import inspect

from .database import engine

_API_DIR = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    cfg = Config(str(_API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_API_DIR / "migrations"))
    return cfg


def _column_names(inspector, table: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table)}


def detect_current_revision(inspector) -> str | None:
    """按哨兵链判定无版本表库的结构落点；完全空库返回 None。

    每个元组为 (revision_id, 该迁移完成后必然存在的首个对象)。"""
    stages = [
        ("0001_legacy_baseline", lambda i: i.has_table("merchants")),
        ("0002_p1_materialized_columns", lambda i: "spec_key" in _column_names(i, "products")),
        ("0003_p5_exchange_rates", lambda i: i.has_table("exchange_rates")),
        (
            "0004_p7_scheduling_notify",
            lambda i: "crawl_interval_minutes" in _column_names(i, "merchants"),
        ),
        ("0005_request_rate_events", lambda i: i.has_table("request_rate_events")),
        ("0006_page_views", lambda i: i.has_table("page_views")),
        (
            "0007_snapshot_checked_indexes",
            lambda i: any(
                idx["name"] == "ix_price_snapshots_product_checked"
                for idx in i.get_indexes("price_snapshots")
            ),
        ),
    ]
    reached: str | None = None
    for revision_id, present in stages:
        if not present(inspector):
            break
        reached = revision_id
    return reached


def run_migrations(url: str | None = None) -> None:
    """对 url（默认应用 DATABASE_URL）执行「检测落点 → stamp → upgrade head」。

    url 参数供迁移演练/测试定向到隔离库，生产路径恒用应用同源连接串。"""
    target_url = url or engine.url.render_as_string(hide_password=False)
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", target_url.replace("%", "%%"))

    probe = sa_create_engine(target_url)
    try:
        inspector = inspect(probe)
        if inspector.has_table("alembic_version"):
            pass  # 已纳管：常规升级
        else:
            reached = detect_current_revision(inspector)
            if reached is not None:
                # Alembic 引入前的存量库：结构即 reached，打点后只补增量
                command.stamp(cfg, reached, tag="pre-alembic legacy catch-up")
    finally:
        probe.dispose()

    command.upgrade(cfg, "head")
