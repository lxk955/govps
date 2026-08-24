"""IP 限流（P7 #10）：DB 滑动窗口计数。

旧实现为进程内 `_ip_requests: dict[str, deque]`，多 worker / 重启后窗口即失效；
本模块把「先判后记」的窗口语义原样迁到 request_rate_events 表上：
- 计数：WHERE ip = ? AND created_at >= now - window（命中复合索引）；
- 清理：小概率顺带删除窗口外的旧行，表体量稳定在「最近窗口 × 请求量」量级，
  低频登录接口下无性能压力。
"""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..models import RequestRateEvent

# 每次判定附带的全表清扫概率（无状态、多 worker 安全；错过不补，下次再清）
_SWEEP_PROBABILITY = 0.05


def hit_rate_limited(db: Session, ip: str, *, window_seconds: int, max_requests: int) -> bool:
    """记录一次请求并返回是否已超限（先判后记：窗口内第 max_requests+1 次起返回 True）。

    与旧 deque 版语义一致；调用方负责在返回 False 后继续原有流程
    （本函数只提交自身写入，不影响外层事务）。"""
    now = datetime.now(timezone.utc)
    recent_count = db.scalar(
        select(func.count(RequestRateEvent.id)).where(
            RequestRateEvent.ip == ip,
            RequestRateEvent.created_at >= now - timedelta(seconds=window_seconds),
        )
    ) or 0

    if recent_count >= max_requests:
        _maybe_sweep(db, now=now, window_seconds=window_seconds)
        return True

    db.add(RequestRateEvent(ip=ip))
    db.commit()
    return False


def _maybe_sweep(db: Session, *, now: datetime, window_seconds: int) -> None:
    if random.random() >= _SWEEP_PROBABILITY:
        return
    db.execute(
        delete(RequestRateEvent).where(
            RequestRateEvent.created_at < now - timedelta(seconds=window_seconds)
        )
    )
    db.commit()
