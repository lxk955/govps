"""Alembic 迁移环境：连接串与元数据全部取自应用自身，杜绝两处定义漂移。"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 保证 `app` 包可导入（alembic 命令在 api/ 目录下执行时天然可见；CI/其他 cwd 下兜底）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import DATABASE_URL  # noqa: E402  (已规范化 postgresql+psycopg://)
from app.models import Base  # noqa: E402

config = context.config

# 连接串优先级：ALEMBIC_DATABASE_URL（迁移演练/测试定向隔离库）
#   > 调用方已程序化设置的值（db_migrations.run_migrations(url=...)）> 应用同源 DATABASE_URL
_override = os.environ.get("ALEMBIC_DATABASE_URL")
if _override:
    config.set_main_option("sqlalchemy.url", _override)
elif not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# autogenerate 的对照目标：与运行时完全同一份模型元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式（--sql）：仅生成 DDL 脚本不连库。"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
