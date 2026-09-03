"""SQLite → gzip → R2 备份：快照一致性、保留策略、任务鉴权。R2 用内存桩，禁网。"""

from datetime import date
from pathlib import Path

import gzip
import sqlite3

from app.services.backup import (
    LATEST_KEY,
    consistent_snapshot,
    dated_keys_to_prune,
    gzip_file,
    run_backup,
    sqlite_file_path,
)
from app.services.r2 import _parse_list_keys, _parse_next_token


def test_sqlite_file_path_absolute_and_relative():
    assert sqlite_file_path("sqlite:////app/data/govps.db") == Path("/app/data/govps.db")
    assert sqlite_file_path("sqlite:///./data/govps.db") == Path("./data/govps.db")
    assert sqlite_file_path("sqlite:///:memory:") is None
    assert sqlite_file_path("postgresql+psycopg://x") is None


def test_parse_r2_list_xml():
    xml = """<?xml version="1.0"?>
    <ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
      <IsTruncated>false</IsTruncated>
      <Contents><Key>db/latest.db.gz</Key></Contents>
      <Contents><Key>db/2026-09-03.db.gz</Key></Contents>
    </ListBucketResult>"""
    assert _parse_list_keys(xml) == ["db/latest.db.gz", "db/2026-09-03.db.gz"]
    assert _parse_next_token(xml) is None


def test_consistent_snapshot_roundtrip(tmp_path):
    src = tmp_path / "src.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.execute("INSERT INTO t (v) VALUES ('hello')")
    conn.commit()
    conn.close()

    dest = tmp_path / "snap.db"
    consistent_snapshot(src, dest)
    rows = sqlite3.connect(dest).execute("SELECT v FROM t").fetchall()
    assert rows == [("hello",)]


def test_gzip_roundtrip(tmp_path):
    raw = tmp_path / "a.db"
    raw.write_bytes(b"sqlite-bytes" * 100)
    gz = tmp_path / "a.db.gz"
    size = gzip_file(raw, gz)
    assert size == gz.stat().st_size
    assert gzip.open(gz, "rb").read() == raw.read_bytes()


def test_retention_keeps_week_and_sundays():
    today = date(2026, 9, 3)  # Thursday
    keys = [
        "db/latest.db.gz",
        "db/2026-09-03.db.gz",  # today
        "db/2026-08-28.db.gz",  # 6 days ago, keep daily
        "db/2026-08-27.db.gz",  # 7 days ago, drop unless Sunday — Friday
        "db/2026-08-23.db.gz",  # Sunday, 11 days ago, keep weekly
        "db/2026-08-02.db.gz",  # Sunday, 32 days ago, drop
        "db/notes.txt",
    ]
    drop = dated_keys_to_prune(keys, today)
    assert "db/latest.db.gz" not in drop
    assert "db/2026-09-03.db.gz" not in drop
    assert "db/2026-08-28.db.gz" not in drop
    assert "db/2026-08-23.db.gz" not in drop
    assert "db/2026-08-27.db.gz" in drop
    assert "db/2026-08-02.db.gz" in drop
    assert "db/notes.txt" not in drop


def test_backup_endpoint_requires_token(client):
    r = client.post("/api/tasks/backup-db")
    assert r.status_code == 403
    r = client.post("/api/tasks/backup-db", headers={"X-Task-Token": "wrong"})
    assert r.status_code == 403


def test_backup_endpoint_skips_when_r2_unconfigured(client):
    r = client.post("/api/tasks/backup-db", headers={"X-Task-Token": "test-task-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["skipped"] is True
    assert body["reason"] == "r2 not configured"


class _FakeR2:
    configured = True

    def __init__(self):
        self.store: dict[str, bytes] = {}

    def put_file(self, key, path, content_type="application/gzip"):
        self.store[key] = path.read_bytes()

    def list_keys(self, prefix):
        return [k for k in self.store if k.startswith(prefix)]

    def delete_key(self, key):
        self.store.pop(key, None)


def test_run_backup_uploads_and_prunes(tmp_path, monkeypatch):
    src = tmp_path / "govps.db"
    conn = sqlite3.connect(src)
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO t DEFAULT VALUES")
    conn.commit()
    conn.close()

    monkeypatch.setattr("app.services.backup.settings.DATABASE_URL", f"sqlite:///{src}")
    fake = _FakeR2()
    fake.store["db/2026-01-01.db.gz"] = b"old"

    result = run_backup(r2=fake, today=date(2026, 9, 3))
    assert result["ok"] is True
    assert result["skipped"] is False
    assert result["key"] == "db/2026-09-03.db.gz"
    assert result["latest"] == LATEST_KEY
    assert result["bytes"] > 0
    assert result["gzip_bytes"] > 0
    assert "db/2026-09-03.db.gz" in fake.store
    assert LATEST_KEY in fake.store
    assert gzip.decompress(fake.store[LATEST_KEY])[:15]  # 能解压
    assert "db/2026-01-01.db.gz" in result["pruned"]
    assert "db/2026-01-01.db.gz" not in fake.store
