"""SQLite → gzip → Cloudflare R2 定时备份。

热备走 SQLite Online Backup API（WAL 下不能直接 cp 库文件）。
R2 未配置时 skip，不让 cron / 部署失败。
"""

from __future__ import annotations

import gzip
import logging
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from ..config import settings
from .r2 import R2Client

log = logging.getLogger(__name__)

DAILY_KEEP_DAYS = 7
WEEKLY_KEEP_DAYS = 28
KEY_PREFIX = "db/"
LATEST_KEY = f"{KEY_PREFIX}latest.db.gz"


def sqlite_file_path(url: str) -> Path | None:
    """从 SQLAlchemy URL 抽出 SQLite 文件路径；非 sqlite 返回 None。"""
    if not url.startswith("sqlite"):
        return None
    rest = url.split(":///", 1)[-1] if ":///" in url else ""
    if not rest or rest == ":memory:":
        return None
    # sqlite:////app/data/x.db → 四斜杠绝对路径
    if url.startswith("sqlite:////"):
        return Path("/" + url.split("sqlite:////", 1)[1])
    return Path(rest)


def consistent_snapshot(src: Path, dest: Path) -> None:
    """在线一致快照，含 WAL 已提交帧；不停止读写。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        dst_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def gzip_file(src: Path, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as fin, gzip.open(dest, "wb", compresslevel=6) as fout:
        while chunk := fin.read(1024 * 1024):
            fout.write(chunk)
    return dest.stat().st_size


def dated_keys_to_prune(keys: list[str], today: date) -> list[str]:
    """保留近 7 天每日 + 近 4 周的周日份；latest 永不删。"""
    drop: list[str] = []
    for key in keys:
        name = key.rsplit("/", 1)[-1]
        if name == "latest.db.gz":
            continue
        if not name.endswith(".db.gz"):
            continue
        stamp = name[: -len(".db.gz")]
        try:
            d = date.fromisoformat(stamp)
        except ValueError:
            continue
        age = (today - d).days
        keep_daily = 0 <= age < DAILY_KEEP_DAYS
        keep_weekly = 0 <= age < WEEKLY_KEEP_DAYS and d.weekday() == 6
        if not (keep_daily or keep_weekly):
            drop.append(key)
    return drop


def run_backup(*, r2: R2Client | None = None, today: date | None = None) -> dict:
    """打一份一致快照，gzip 后上传 R2，并按保留策略删旧对象。"""
    db_path = sqlite_file_path(settings.DATABASE_URL)
    if db_path is None:
        return {"ok": True, "skipped": True, "reason": "not sqlite"}
    if not db_path.exists():
        return {"ok": False, "error": f"sqlite file not found: {db_path}"}

    client = r2 or R2Client()
    if not client.configured:
        return {"ok": True, "skipped": True, "reason": "r2 not configured"}

    day = today or datetime.now(timezone.utc).date()
    daily_key = f"{KEY_PREFIX}{day.isoformat()}.db.gz"

    with tempfile.TemporaryDirectory(prefix="govps-backup-") as tmp:
        tmp_dir = Path(tmp)
        snap = tmp_dir / "govps.db"
        gz = tmp_dir / "govps.db.gz"
        consistent_snapshot(db_path, snap)
        raw_bytes = snap.stat().st_size
        gzip_bytes = gzip_file(snap, gz)
        client.put_file(daily_key, gz)
        client.put_file(LATEST_KEY, gz)

    pruned: list[str] = []
    try:
        existing = client.list_keys(KEY_PREFIX)
        for key in dated_keys_to_prune(existing, day):
            client.delete_key(key)
            pruned.append(key)
    except Exception as e:
        # 上传已成功；清理失败不让整次备份算失败
        log.warning("R2 prune failed: %s", e)

    return {
        "ok": True,
        "skipped": False,
        "key": daily_key,
        "latest": LATEST_KEY,
        "bytes": raw_bytes,
        "gzip_bytes": gzip_bytes,
        "pruned": pruned,
    }
