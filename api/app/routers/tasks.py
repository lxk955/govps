from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..services.notify import process_pending_emails
from ..services.rates import update_rates
from ..services.scan import run_scan

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/scan")
def scan(
    force: bool = Query(default=False, description="忽略分级调度到期判断，强制抓取全部商家"),
    x_task_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """由 cron-job.org 周期调用：按商家分级调度抓取到期者 → 比对 → 入队通知。
    force=true 时忽略到期判断全量抓取（手动补扫用）。"""
    if x_task_token != settings.TASK_TOKEN:
        raise HTTPException(status_code=403, detail="invalid task token")
    return run_scan(db, force=force)


class UpdateRatesIn(BaseModel):
    """人工覆盖入口（运维工具，无 UI）：{"overrides": {"CNY": 7.25}}。
    覆盖不受自动源漂移守卫限制，source 标记为 manual；留空则走自动源。"""

    overrides: dict[str, float] | None = None


@router.post("/update-rates")
def update_rates_task(
    x_task_token: str | None = Header(default=None),
    payload: UpdateRatesIn | None = None,
    db: Session = Depends(get_db),
):
    """每日由 cron 调用：拉取汇率并写当日快照；断源时保留旧值不报错污染。
    携带 overrides 即人工覆盖异常汇率。"""
    if x_task_token != settings.TASK_TOKEN:
        raise HTTPException(status_code=403, detail="invalid task token")
    return update_rates(db, overrides=payload.overrides if payload else None)


@router.post("/process-emails")
def process_emails_task(
    x_task_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """消费 pending NotifyLog（P7 邮件异步化的 cron 兜底入口）。

    常态由进程内 notify-worker 线程周期消费；本端点用于：
    NOTIFY_WORKER_ENABLED=false 的部署形态、多实例下由 cron 统一驱动、
    以及人工补发排查。幂等——仅 pending 行会被处理，已 sent/failed 不重发。"""
    if x_task_token != settings.TASK_TOKEN:
        raise HTTPException(status_code=403, detail="invalid task token")
    return process_pending_emails(db)
