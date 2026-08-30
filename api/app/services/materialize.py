"""扫描期物化（refactor-plan §2 #1/#9 修复）：评分、聚合键、搜索文本的计算时机
从「每次列表请求」迁移到「每次扫描结束后一次」，公式与语义零改动。

- 列表请求改为读取物化列并下推过滤/排序到 SQL，消除全表加载与逐条实时评分。
- 物化值随每次 run_scan 全量刷新；关注数/点击数等时变信号因此有最长一个
  扫描周期的滞后——这是方案明确接受的权衡（§8 风险登记第 1 条）。
- 所有写入均为可空列赋值，向后兼容（refactor-plan §4）。
"""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import AffClick, NotifyEvent, Product, Watchlist
from .scoring import _product_search_text, calculate_scores_and_reasons, spec_group_key


def compute_spec_key(p: Product) -> str:
    """spec_group_key 元组的规范化 JSON 序列化。

    用 JSON 数组而非拼接符连接，杜绝名称含分隔符导致的键碰撞；
    各元素经显式类型规范化，保证同一逻辑分组在任何进程/平台产出同一字符串。"""
    key = spec_group_key(p)
    return json.dumps(
        [
            str(key[0]),
            key[1],
            key[2],
            ";".join(key[3]),
            str(key[4]),
            repr(key[5]),
            str(key[6]),
            str(key[7]),
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def fill_static_fields(p: Product) -> None:
    """upsert 时即可确定的物化字段（聚合键 / 搜索文本 / 线路文本）。"""
    p.spec_key = compute_spec_key(p)
    p.search_text = _product_search_text(p)
    p.line_tags_text = " ".join(str(t) for t in (p.line_tags or [])).lower() or None


def engagement_snapshot(db: Session) -> dict:
    """一次性收集热度指标（关注数、点击总量/近7天/近3小时、48h 补货与降价集合）。

    与旧 list_products 内联查询完全同构；由每请求一次降为每扫描一次。"""
    now = datetime.now(timezone.utc)
    t_3h = now - timedelta(hours=3)
    t_7d = now - timedelta(days=7)
    t_48h = now - timedelta(hours=48)
    return {
        "watch_counts": dict(
            db.execute(
                select(Watchlist.product_id, func.count(Watchlist.id)).group_by(Watchlist.product_id)
            ).all()
        ),
        "clicks_total": dict(
            db.execute(
                select(AffClick.product_id, func.count(AffClick.id)).group_by(AffClick.product_id)
            ).all()
        ),
        "clicks_7d": dict(
            db.execute(
                select(AffClick.product_id, func.count(AffClick.id))
                .where(AffClick.created_at >= t_7d)
                .group_by(AffClick.product_id)
            ).all()
        ),
        "clicks_3h": dict(
            db.execute(
                select(AffClick.product_id, func.count(AffClick.id))
                .where(AffClick.created_at >= t_3h)
                .group_by(AffClick.product_id)
            ).all()
        ),
        "restocked_48h": set(
            db.scalars(
                select(NotifyEvent.product_id).where(
                    NotifyEvent.type == "RESTOCK", NotifyEvent.created_at >= t_48h
                )
            ).all()
        ),
        "dropped_48h": set(
            db.scalars(
                select(NotifyEvent.product_id).where(
                    NotifyEvent.type == "PRICE_DROP", NotifyEvent.created_at >= t_48h
                )
            ).all()
        ),
    }


def score_product(p: Product, snap: dict) -> None:
    """按既有公式计算并把评分/理由落到物化列（公式零改动）。"""
    deal_s, pop_s, hot_s, reasons = calculate_scores_and_reasons(
        p,
        watch_count=snap["watch_counts"].get(p.id, 0),
        total_clicks=snap["clicks_total"].get(p.id, 0),
        clicks_7d=snap["clicks_7d"].get(p.id, 0),
        clicks_3h=snap["clicks_3h"].get(p.id, 0),
        is_recent_restock=(p.id in snap["restocked_48h"]),
        is_recent_drop=(p.id in snap["dropped_48h"]),
    )
    p.deal_score = deal_s
    p.popularity_score = pop_s
    p.hot_score = hot_s
    p.score_reasons = reasons


def refresh_derived_fields(db: Session) -> int:
    """全量刷新物化列（run_scan 收尾与启动回填共用）；返回刷新行数。不负责 commit。"""
    fill_missing_static(db)
    snap = engagement_snapshot(db)
    n = 0
    for p in db.scalars(select(Product)).all():
        score_product(p, snap)
        n += 1
    db.flush()
    return n


def fill_missing_static(db: Session) -> int:
    """仅为缺失聚合键/搜索文本的行补齐（启动回填旧库用；正常扫描路径已实时维护）。"""
    n = 0
    for p in db.scalars(
        select(Product)
        .options(joinedload(Product.merchant))
        .where(Product.spec_key.is_(None))
    ).all():
        fill_static_fields(p)
        n += 1
    if n:
        db.flush()
    return n
