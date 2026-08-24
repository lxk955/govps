"""Pytest bootstrap: env must be set before importing app.database / app.main."""

import os
from pathlib import Path

_DB = Path(__file__).resolve().parent / "_pytest.sqlite3"
if _DB.exists():
    _DB.unlink()

os.environ["SKIP_STARTUP_SCAN"] = "1"
# P7：测试进程内不启动邮件后台线程，worker 执行体由用例显式调用
os.environ["NOTIFY_WORKER_ENABLED"] = "0"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["TASK_TOKEN"] = "test-task-token"
os.environ["RESEND_API_KEY"] = ""
os.environ["PUBLIC_API_URL"] = "http://testserver"
os.environ["CORS_ORIGINS"] = "http://testserver"

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(db):
    from app.main import app

    with TestClient(app) as c:
        yield c
