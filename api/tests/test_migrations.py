"""Alembic 迁移链完整性测试（P7，refactor-plan §2 #8 / §4）。零外网、隔离临时 SQLite。

- parity：`upgrade head` 的最终结构与 Base.metadata.create_all 逐表一致
  （表集合 / 列名+类型+可空 / 主键 / 索引 / 唯一约束），防止模型与迁移漂移；
- legacy catch-up：旧库（仅 baseline 结构 + 存量数据）经 run_migrations
  stamp → 增量升级到 head 后结构补齐、数据保留；
- 哨兵判定：对中间形态给出正确落点。
"""

import tempfile
from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.db_migrations import alembic_config, detect_current_revision, run_migrations

HEAD = "0006_page_views"
EXPECTED_TABLES = set(Base.metadata.tables.keys())  # 全部业务模型表


def _upgrade(url: str, rev: str = "head") -> None:
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, rev)


def _snapshot(url: str) -> dict:
    """库结构的可比较快照（不含 alembic_version 等内部表）。"""
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        snap = {}
        for t in insp.get_table_names():
            if t == "alembic_version":
                continue
            snap[t] = {
                "cols": {c["name"]: (str(c["type"]), bool(c["nullable"])) for c in insp.get_columns(t)},
                "pk": tuple(sorted(insp.get_pk_constraint(t)["constrained_columns"])),
                "idx": {i["name"]: (tuple(i["column_names"]), bool(i.get("unique"))) for i in insp.get_indexes(t)},
                "uqs": {u["name"]: tuple(sorted(u["column_names"])) for u in insp.get_unique_constraints(t)},
            }
        return snap
    finally:
        eng.dispose()


def _tmp_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{tmp_path / name}"


def test_upgrade_head_matches_models_exactly(tmp_path):
    url = _tmp_url(tmp_path, "migrated.db")
    _upgrade(url)

    created_db = _tmp_url(tmp_path, "created.db")
    eng = create_engine(created_db)
    try:
        Base.metadata.create_all(eng)
    finally:
        eng.dispose()

    migrated, created = _snapshot(url), _snapshot(created_db)
    assert set(migrated) == EXPECTED_TABLES, "迁移链必须覆盖全部业务表且不多不少"
    assert migrated == created, "upgrade head 与 create_all 结构不一致（模型/迁移漂移）"


def test_empty_db_run_migrations_builds_to_head_and_stamps(tmp_path):
    url = _tmp_url(tmp_path, "fresh.db")
    run_migrations(url=url)          # 生产 startup 路径（空库分支）
    eng = create_engine(url)
    try:
        assert inspect(eng).has_table("alembic_version")
        with eng.connect() as conn:
            (num,) = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    finally:
        eng.dispose()
    assert num == HEAD


def test_sentinel_detection_on_intermediate_states(tmp_path):
    url = _tmp_url(tmp_path, "legacy.db")
    _upgrade(url, "0001_legacy_baseline")     # 仅旧库形态
    insp = inspect(create_engine(url))
    assert detect_current_revision(insp) == "0001_legacy_baseline"

    run_migrations(url=url)                   # 补齐增量
    insp2 = inspect(create_engine(url))
    assert detect_current_revision(insp2) == HEAD
    assert "spec_key" in {c["name"] for c in insp2.get_columns("products")}
    assert "crawl_interval_minutes" in {c["name"] for c in insp2.get_columns("merchants")}
    assert insp2.has_table("request_rate_events")


def test_legacy_catch_up_preserves_data(tmp_path):
    """存量旧库升级路径：baseline 结构 + 业务数据 → run_migrations → 数据原样保留。"""
    from datetime import datetime, timezone
    from decimal import Decimal

    url = _tmp_url(tmp_path, "prod_like.db")
    _upgrade(url, "0001_legacy_baseline")

    eng = create_engine(url)
    try:
        with eng.begin() as conn:
            conn.execute(
                text("INSERT INTO merchants (id, slug, name, website, enabled, last_success_at, last_error)"
                     " VALUES (1, 'oldshop', 'OldShop', 'https://old.example', 1, NULL, NULL)")
            )
            conn.execute(
                text("INSERT INTO products (id, merchant_id, external_id, name, line_tags, price,"
                     " currency, billing_cycle, price_options, purchase_url, in_stock, recommended,"
                     " created_at, updated_at)"
                     " VALUES (11, 1, 'old-1', 'Legacy Plan', '[]', 9.99, 'USD', 'monthly', '[]',"
                     " 'https://old.example/buy', 1, 0, :now, :now)"),
                {"now": datetime.now(timezone.utc)},
            )
    finally:
        eng.dispose()

    run_migrations(url=url)

    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            name, price = conn.execute(
                text("SELECT name, price FROM products WHERE id = 11")
            ).fetchone()
            (slug,) = conn.execute(text("SELECT slug FROM merchants WHERE id = 1")).fetchone()
            (version,) = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            # 新增列对旧行为 NULL（可空增量列，回滚无需 DB 动作）
            (spec_key,) = conn.execute(text("SELECT spec_key FROM products WHERE id = 11")).fetchone()
    finally:
        eng.dispose()

    assert slug == "oldshop"
    assert float(price) == float(Decimal("9.99"))
    assert spec_key is None                      # 回填由扫描收尾 refresh_derived_fields 负责
    assert version == HEAD


def test_downgrade_chain_executes_cleanly_through_all_versions(tmp_path):
    """P7/P8 门禁断言：全部 5 个版本的 downgrade 路径均实际执行并验证。

    回滚行为断言：
    - 0005 -> 0004: 删除 request_rate_events 表与两个索引；
    - 0004 -> 0003: 删除 merchants.crawl_interval_minutes 与 notify_logs.attempts；
    - 0003 -> 0002: 删除 exchange_rates 与 exchange_rate_snapshots 表；
    - 0002 -> 0001: 删除 products 物化列与 ix_products_merchant_spec 索引；
    - 0001 -> base: 清理 baseline 全部 10 张业务表，库回到纯净 base 状态。
    """
    url = _tmp_url(tmp_path, "downgrade_test.db")
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", url)

    # 1. 先升至最新 head (0006)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert insp.has_table("request_rate_events")
        assert "crawl_interval_minutes" in {c["name"] for c in insp.get_columns("merchants")}
        assert insp.has_table("exchange_rates")
        assert "spec_key" in {c["name"] for c in insp.get_columns("products")}
        assert insp.has_table("merchants")
    finally:
        eng.dispose()

    # 2. 0005 -> 0004
    command.downgrade(cfg, "0004_p7_scheduling_notify")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert not insp.has_table("request_rate_events")
        assert "crawl_interval_minutes" in {c["name"] for c in insp.get_columns("merchants")}
    finally:
        eng.dispose()

    # 3. 0004 -> 0003
    command.downgrade(cfg, "0003_p5_exchange_rates")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert "crawl_interval_minutes" not in {c["name"] for c in insp.get_columns("merchants")}
        assert insp.has_table("exchange_rates")
    finally:
        eng.dispose()

    # 4. 0003 -> 0002
    command.downgrade(cfg, "0002_p1_materialized_columns")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert not insp.has_table("exchange_rates")
        assert not insp.has_table("exchange_rate_snapshots")
        assert "spec_key" in {c["name"] for c in insp.get_columns("products")}
    finally:
        eng.dispose()

    # 5. 0002 -> 0001
    command.downgrade(cfg, "0001_legacy_baseline")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        assert "spec_key" not in {c["name"] for c in insp.get_columns("products")}
        assert insp.has_table("products")
    finally:
        eng.dispose()

    # 6. 0001 -> base (清理全量业务表)
    command.downgrade(cfg, "base")
    eng = create_engine(url)
    try:
        insp = inspect(eng)
        remaining = [t for t in insp.get_table_names() if t != "alembic_version"]
        assert remaining == [], f"0001 baseline downgrade 必须清理全部业务表，剩余: {remaining}"
    finally:
        eng.dispose()


def test_real_legacy_vps_scout_db_migration_dry_run(tmp_path):
    """P8 门禁断言：使用真实旧版生产库副本（vps-scout/api/vps_scout.db）执行迁移演练。
    验证哨兵识别、stamp 准确性、数据 100% 保持及物化列可刷新。"""
    import shutil
    from app.services.materialize import refresh_derived_fields
    from sqlalchemy.orm import Session

    real_legacy = Path("/home/kk/workspace/vps-scout/api/vps_scout.db")
    if not real_legacy.exists():
        # 若在纯净 CI 机器无旧库物理文件，跳过
        return

    dst = tmp_path / "real_prod_copy.db"
    shutil.copyfile(real_legacy, dst)
    url = f"sqlite:///{dst}"

    eng = create_engine(url)
    insp_before = inspect(eng)
    with eng.connect() as conn:
        m_before = conn.execute(text("SELECT count(*) FROM merchants")).scalar()
        p_before = conn.execute(text("SELECT count(*) FROM products")).scalar()
        c_before = conn.execute(text("SELECT count(*) FROM aff_clicks")).scalar()

    # 1. 验证哨兵识别旧库为 0001_legacy_baseline
    assert detect_current_revision(insp_before) == "0001_legacy_baseline"

    # 2. 运行增量迁移
    run_migrations(url=url)

    # 3. 验证数据 100% 保留
    with eng.connect() as conn:
        (ver,) = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert ver == HEAD
        m_after = conn.execute(text("SELECT count(*) FROM merchants")).scalar()
        p_after = conn.execute(text("SELECT count(*) FROM products")).scalar()
        c_after = conn.execute(text("SELECT count(*) FROM aff_clicks")).scalar()
        assert (m_before, p_before, c_before) == (m_after, p_after, c_after)

    # 4. 验证物化列刷新成功
    with Session(eng) as s:
        refreshed = refresh_derived_fields(s)
        assert refreshed == p_after


