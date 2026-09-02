"""从 Neon PostgreSQL 数据库全量高保真迁移数据到本地 SQLite 数据库。"""

import os
import sys
from pathlib import Path
import sqlalchemy as sa
from sqlalchemy.orm import Session

# 确保项目模块可引用
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "api"))

from app.database import Base
from app import models  # 注册所有 ORM 模型

PG_URL = os.getenv("SOURCE_PG_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")
if not PG_URL:
    print("错误: 请提供源 PostgreSQL 连接串。例如: SOURCE_PG_URL='postgresql://...' python migrate_pg_to_sqlite.py")
    sys.exit(1)

TARGET_SQLITE_PATH = ROOT_DIR / "data" / "govps.db"

TABLES_IN_ORDER = [
    "alembic_version",
    "merchants",
    "users",
    "products",
    "price_snapshots",
    "stock_snapshots",
    "notify_events",
    "notify_logs",
    "watchlist",
    "email_codes",
    "exchange_rates",
    "exchange_rate_snapshots",
    "aff_clicks",
    "page_views",
    "request_rate_events",
]


def run_migration():
    print(f"==> Source PostgreSQL: {PG_URL.split('@')[1] if '@' in PG_URL else PG_URL}")
    print(f"==> Target SQLite: {TARGET_SQLITE_PATH}")

    # 1. 确保目标目录存在并清理旧数据文件
    TARGET_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if TARGET_SQLITE_PATH.exists():
        TARGET_SQLITE_PATH.unlink()
    for extra in [f"{TARGET_SQLITE_PATH}-wal", f"{TARGET_SQLITE_PATH}-shm"]:
        if os.path.exists(extra):
            os.unlink(extra)

    src_engine = sa.create_engine(PG_URL, pool_pre_ping=True)
    tgt_engine = sa.create_engine(
        f"sqlite:///{TARGET_SQLITE_PATH}",
        connect_args={"check_same_thread": False},
    )

    # 2. 在目标 SQLite 创建完整的表结构与索引
    print("==> Creating tables in SQLite...")
    Base.metadata.create_all(bind=tgt_engine)

    # 如果有 alembic_version 表，确保它也存在
    with tgt_engine.connect() as tgt_conn:
        tgt_conn.execute(
            sa.text(
                "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
            )
        )
        tgt_conn.commit()

    # 3. 按依赖顺序迁移数据
    src_meta = sa.MetaData()
    src_meta.reflect(bind=src_engine)

    tgt_meta = sa.MetaData()
    tgt_meta.reflect(bind=tgt_engine)

    with tgt_engine.connect() as tgt_conn, src_engine.connect() as src_conn:
        tgt_conn.execute(sa.text("PRAGMA foreign_keys = OFF;"))
        tgt_conn.execute(sa.text("PRAGMA journal_mode = WAL;"))
        tgt_conn.commit()

        total_rows = 0
        for table_name in TABLES_IN_ORDER:
            if table_name not in src_meta.tables:
                print(f"[-] Skip {table_name} (not found in source)")
                continue

            src_table = src_meta.tables[table_name]
            tgt_table = tgt_meta.tables[table_name]

            # 查询源表全部数据
            rows = src_conn.execute(sa.select(src_table)).mappings().all()
            count = len(rows)
            total_rows += count

            if count > 0:
                # 批量分块插入
                chunk_size = 500
                for i in range(0, count, chunk_size):
                    chunk = [dict(r) for r in rows[i : i + chunk_size]]
                    tgt_conn.execute(tgt_table.insert(), chunk)
                tgt_conn.commit()

            print(f"[✓] {table_name:25s} -> Migrated {count:5d} rows")

        # 4. 验证外键与行数
        tgt_conn.execute(sa.text("PRAGMA foreign_keys = ON;"))
        tgt_conn.commit()

    print(f"\n🎉 迁移全部完成！共迁移 {total_rows} 条记录到 {TARGET_SQLITE_PATH}")

    # 同时备份一份到 api/govps.db 保持开发环境同步
    api_db = ROOT_DIR / "api" / "govps.db"
    import shutil
    shutil.copy2(TARGET_SQLITE_PATH, api_db)
    print(f"==> 同步备份已复制至: {api_db}")


if __name__ == "__main__":
    run_migration()
