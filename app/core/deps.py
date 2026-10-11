# FastAPI 依赖：数据库会话、操作员占位鉴权

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import ApiError, ErrorCode


def get_db() -> Iterator[Session]:
    """请求级数据库会话；测试通过 dependency_overrides 替换。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def require_operator(request: Request) -> str:
    """写接口最小鉴权占位：必须携带 X-Operator-ID。"""
    operator_id = (request.headers.get("X-Operator-ID") or "").strip()
    if not operator_id:
        raise ApiError(401, ErrorCode.UNAUTHORIZED, "缺少操作员标识 X-Operator-ID")
    return operator_id


def optional_operator(request: Request) -> str | None:
    operator_id = (request.headers.get("X-Operator-ID") or "").strip()
    return operator_id or None
