#!/usr/bin/env python3
"""部署重建前打一份本地 SQLite 一致快照（gzip）。

由 GitHub Actions SSH 脚本调用；WAL 下不能 cp 正在写的 .db。
库文件不存在则跳过（首次部署）。
"""

from __future__ import annotations

import gzip
import sqlite3
import sys
from pathlib import Path

SRC = Path("/opt/govps/data/govps.db")
TMP = Path("/tmp/govps-pre-migrate.db")
OUT = Path("/opt/govps/data/govps-pre-migrate.db.gz")


def main() -> int:
    if not SRC.exists():
        print("no db yet, skip local snapshot")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(TMP)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    with TMP.open("rb") as fin, gzip.open(OUT, "wb", compresslevel=6) as fout:
        while chunk := fin.read(1024 * 1024):
            fout.write(chunk)
    TMP.unlink(missing_ok=True)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
