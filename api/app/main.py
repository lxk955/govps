from pathlib import Path
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .routers import auth, events, go, ipcheck, products, rates, stats, tasks, track, watchlist

app = FastAPI(title="VPS 雷达 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(products.router)
app.include_router(rates.router)
app.include_router(watchlist.router)
app.include_router(tasks.router)
app.include_router(go.router)
app.include_router(ipcheck.router)
app.include_router(track.router)
app.include_router(stats.router)

# 非实时只读 GET：短缓存。库存/价格/关注/鉴权一律走默认 no-store。
_API_CACHE_GET: dict[str, str] = {
    "/api/products/merchants": "public, max-age=60, stale-while-revalidate=120",
    "/api/events/summary": "public, max-age=60, stale-while-revalidate=240",
    "/api/rates": "public, max-age=300, stale-while-revalidate=600",
    "/api/rates/snapshots": "public, max-age=300, stale-while-revalidate=600",
}


@app.on_event("startup")
def init_db():
    # 建库走版本化迁移（P7，refactor-plan §2 #8 / §4）：空库 upgrade 到 head；
    # 存量旧库按哨兵判定落点 stamp 后增量升级；手写补列 ALTER 链就此废除。
    try:
        from .db_migrations import run_migrations
        run_migrations()
        print("[startup] DB migrations executed successfully.")
    except Exception as e:
        print(f"[startup] DB migration notice: {e}")

    # 汇率兜底：表为空时拉一次。cron 若未配置 update-rates，部署后也能立即有
    # 换算价，不至于长期缺失（非 USD 价格将一直显示原币且无法比价）。
    # 已有汇率则不动——沿用旧值，与 update_rates「断源保留旧值」的语义一致；
    # 日更由 scan 收尾的 maybe_update_rates 负责，这里只兜「从来没有」。
    try:
        from sqlalchemy import select

        from .config import settings as _s
        from .database import SessionLocal
        from .models import ExchangeRate
        from .services.rates import update_rates

        with SessionLocal() as db:
            # 不能用 current_rates_map(db) 判空：它总会 setdefault 一个 USD 基准
            # （见 rates.current_rates_map），永远非空。这里直接查是否已有非 USD
            # 的真实汇率行——没有就说明从未成功拉过汇率。
            has_real_rate = db.scalar(
                select(ExchangeRate.code).where(ExchangeRate.code != "USD").limit(1)
            )
            if has_real_rate is None and not _s.SKIP_AUTO_RATES:
                res = update_rates(db)
                print(f"[startup] exchange rates bootstrapped: {res}")
    except Exception as e:
        print(f"[startup] exchange rate bootstrap notice: {e}")

    # 启动时全量扫描（复用 run_scan，与定时任务行为一致：含消失商品标记缺货、
    # 事件去重与通知。停机期间下架的商品在重启后立即被纠正）
    try:
        from .database import SessionLocal
        from .services.scan import run_scan

        with SessionLocal() as db:
            if not settings.SKIP_STARTUP_SCAN:
                result = run_scan(db)
                print(f"[startup] scan done: {result['summary']}")

            # 只补缺失聚合键（旧库升级 / 测试直插）。机房规范化、精选 SKU、
            # 全量评分由 run_scan 收尾负责，避免每次冷启动扫全表。
            from .services.materialize import fill_missing_static

            filled = fill_missing_static(db)
            db.commit()
            if filled:
                print(f"[startup] missing spec_key filled: {filled}")
    except Exception as err:
        print(f"[startup] merchant sync warning: {err}")


@app.middleware("http")
async def api_cache_control(request, call_next):
    """库存/价格接口禁止缓存；商家计数、事件摘要、汇率可短缓存。

    全站 /api/* 默认 no-store，避免 Cloudflare 把缺货/涨价回成旧状态
    （AGENTS.md Data Freshness）。商家列表与 24h 计数不是实时库存，
    允许短 max-age，减轻首页重复回源。
    """
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        return response
    path = request.url.path.rstrip("/") or "/"
    if request.method == "GET" and path in _API_CACHE_GET:
        response.headers["Cache-Control"] = _API_CACHE_GET[path]
    else:
        response.headers["Cache-Control"] = "no-store"
    return response


def _notify_worker_loop() -> None:
    """P7 邮件异步 worker：周期消费 pending NotifyLog。
    DB-backed outbox——进程重启后 pending 行自然被重新拾取，不丢不重。"""
    from .database import SessionLocal
    from .services.notify import process_pending_emails

    while True:
        try:
            with SessionLocal() as db:
                result = process_pending_emails(db)
                if result["processed"]:
                    print(f"[notify-worker] {result}")
        except Exception as err:
            print(f"[notify-worker] error: {err}")
        time.sleep(settings.NOTIFY_WORKER_INTERVAL_SECONDS)


if settings.NOTIFY_WORKER_ENABLED:
    threading.Thread(target=_notify_worker_loop, daemon=True, name="notify-worker").start()


@app.get("/api/health")
def health():
    return {"ok": True}


# ── 前端静态文件（单容器部署：前端构建产物已打包进镜像的 ./static）──
# 所有非 /api 路径都交给 SPA：有对应文件就返回文件，否则回退到 index.html
STATIC_DIR = (Path(__file__).resolve().parent.parent / "static").resolve()


@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    # resolve 后校验仍在静态目录内：URL 编码的 ../ 或绝对路径（%2Fetc%2Fpasswd）
    # 会被路由参数解码还原，不做包含性校验会构成任意文件读取
    try:
        target = (STATIC_DIR / full_path).resolve()
        inside = target.is_relative_to(STATIC_DIR)
    except (OSError, ValueError):
        inside = False
    if full_path and inside and target.is_file():
        return FileResponse(target)
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="Not Found")
