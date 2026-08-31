#!/usr/bin/env python3
"""一次性运维脚本：统一商家抓取间隔（2026-08-31 运营决策：全商家 5 分钟）。

背景：P7 分级调度下 adapter 默认值只在 merchants.crawl_interval_minutes 为
NULL 时写入（ensure_merchants 不覆盖运营已设值），因此改代码默认值不会影响
生产库中已初始化的行——本脚本负责把存量行刷成新口径。

用法（在 api 目录下，DATABASE_URL 指向目标库）：
    DATABASE_URL=postgresql://... .venv/bin/python scripts/set_crawl_interval.py           # 预览（dry-run）
    DATABASE_URL=postgresql://... .venv/bin/python scripts/set_crawl_interval.py --apply   # 实际执行
    DATABASE_URL=postgresql://... .venv/bin/python scripts/set_crawl_interval.py --apply --minutes 10  # 自定义值

仅改动 merchants 表 crawl_interval_minutes 列，不触碰其他数据。
"""

import argparse
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from sqlalchemy import create_engine, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models import Merchant  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="统一 merchants.crawl_interval_minutes")
    parser.add_argument("--apply", action="store_true", help="实际写入（默认仅预览）")
    parser.add_argument("--minutes", type=int, default=5, help="目标间隔分钟数（默认 5）")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("错误：未设置 DATABASE_URL 环境变量", file=sys.stderr)
        return 1
    # Neon/Heroku 风格 postgres:// 统一为 postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(url)
    with Session(engine) as db:
        rows = list(db.scalars(select(Merchant).order_by(Merchant.id)).all())
        if not rows:
            print("库中无商家行，无需改动。")
            return 0

        print(f"{'id':>4}  {'slug':<12} {'旧值':>5}  新值")
        changed = 0
        for m in rows:
            old = m.crawl_interval_minutes
            mark = "" if old == args.minutes else "  ← 改"
            print(f"{m.id:>4}  {m.slug:<12} {str(old):>5}  {args.minutes}{mark}")
            if old != args.minutes:
                changed += 1

        if not changed:
            print("\n全部行已是目标值，无需改动。")
            return 0

        if not args.apply:
            print(f"\n[dry-run] 将更新 {changed} 行。确认无误后加 --apply 执行。")
            return 0

        db.execute(
            update(Merchant).where(Merchant.crawl_interval_minutes != args.minutes),
            {"crawl_interval_minutes": args.minutes},
        )
        db.commit()
        print(f"\n已更新 {changed} 行 crawl_interval_minutes = {args.minutes}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
