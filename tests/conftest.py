# 测试基础设施：独立临时 SQLite 库 + get_db 依赖覆盖
#
# 测试不触碰 data/sqlite_demo.db：每个用例在 tmp_path 下建库，
# 通过 dependency_overrides 注入请求级会话。

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  # 确保模型已注册到 Base.metadata
from app.core import database as db_module
from app.core.deps import get_db
from app.db import apply_baseline
from app.main import app


@pytest.fixture()
def db_session(tmp_path: Path) -> Iterator[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    db_module.Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def seeded_db_session(db_session: Session) -> Session:
    """在临时库中灌入 baseline-v1 演示数据（退款/不良反应/补发三场景固定入口）。"""
    apply_baseline(db_session)
    db_session.commit()
    return db_session


@pytest.fixture()
def seeded_client(seeded_db_session: Session) -> Iterator[TestClient]:
    """带演示数据的 TestClient：与真实 demo 库隔离，逐用例独立建库。"""

    def override_get_db() -> Iterator[Session]:
        yield seeded_db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
