#!/usr/bin/env python3
"""手动爬虫在线检查脚本（refactor-plan §5 / §8；不进入 CI）。

用法：
    python scripts/crawl_live_check.py                    # 检查全部 7 家
    python scripts/crawl_live_check.py --slug bandwagon   # 仅检查指定商家
    python scripts/crawl_live_check.py --verbose          # 输出各商家抓取到的产品样例

原则（AGENTS.md Crawler Testing）：
- 常规 CI 测试严禁访问公网（一律走 fixtures 回放）；
- 本脚本仅供人工运维排查、商家改版核验及 fixture 录制前验证使用。
"""

import argparse
import sys
import time
from pathlib import Path

# 保证能直接从 api 根目录或脚本目录运行
API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR))

from app.crawler.base import make_client
from app.crawler.registry import CRAWLERS


def main() -> int:
    parser = argparse.ArgumentParser(description="GoVPS 爬虫在线连通与解析核验脚本")
    parser.add_argument("--slug", help="仅检查指定 slug 的商家（如 dmit, bandwagon, dedione 等）")
    parser.add_argument("--timeout", type=float, default=20.0, help="单商家抓取超时秒数（默认 20s）")
    parser.add_argument("--verbose", "-v", action="store_true", help="打印详细样本输出")
    args = parser.parse_args()

    crawlers = CRAWLERS
    if args.slug:
        crawlers = [c for c in CRAWLERS if c.slug == args.slug]
        if not crawlers:
            print(f"错误: 未找到 slug 为 '{args.slug}' 的爬虫。可选: {[c.slug for c in CRAWLERS]}")
            return 1

    print(f"=== GoVPS 爬虫在线检查 (共 {len(crawlers)} 家商家) ===")
    print(f"{'商家':<12} | {'耗时':<8} | {'抓取款数':<8} | {'在售款数':<8} | {'默认间隔':<8} | 状态")
    print("-" * 72)

    has_error = False
    with make_client(args.timeout) as client:
        for crawler in crawlers:
            t0 = time.perf_counter()
            try:
                raws = crawler.fetch(client)
                elapsed = (time.perf_counter() - t0) * 1000
                total = len(raws)
                in_stock = sum(1 for r in raws if r.in_stock)
                interval = getattr(crawler, "default_interval_minutes", 15)
                status = "OK" if total > 0 else "WARN (0 products)"
                print(
                    f"{crawler.slug:<12} | {elapsed:>6.0f}ms | {total:>8} | {in_stock:>8} | {interval:>6}m | {status}"
                )

                if args.verbose and raws:
                    print(f"  [样例 1/{total}] {raws[0].name} | {raws[0].currency} {raws[0].price}/{raws[0].billing_cycle} | 有货: {raws[0].in_stock}")
                    if len(raws) > 1:
                        print(f"  [样例 2/{total}] {raws[1].name} | {raws[1].currency} {raws[1].price}/{raws[1].billing_cycle} | 有货: {raws[1].in_stock}")
            except Exception as e:
                elapsed = (time.perf_counter() - t0) * 1000
                has_error = True
                print(f"{crawler.slug:<12} | {elapsed:>6.0f}ms | {'-':>8} | {'-':>8} | {'-':>8} | ERROR: {e}")

    print("-" * 72)
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
