# -*- coding: utf-8 -*-
"""
pytest 入口：先于任何 test 模块设置环境，并强制使用本机 SQLite 文件，
避免 .env 中 MySQL 在 CI/无库环境下导致「no such table」。
"""
from __future__ import annotations

import os

_backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_sqlite_file = os.path.join(_backend_root, ".pytest_tujia.sqlite")
# Windows 路径给 SQLAlchemy
_sqlite_url = "sqlite:///" + _sqlite_file.replace("\\", "/")

os.environ["DATABASE_URL"] = _sqlite_url
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-16chars!!")
os.environ["DEBUG"] = "True"
os.environ["HIVE_ANALYTICS_PRIMARY"] = "false"
os.environ.setdefault("HIVE_HEALTH_REQUIRED", "false")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def client() -> TestClient:
    from main import app
    from app.db.database import init_db

    init_db()
    with TestClient(app) as c:
        yield c
