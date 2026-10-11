# 健康检查：服务、数据库与模型网关状态（GET /api/health）
#
# 数据库不可用时返回 HTTP 503 DATABASE_UNAVAILABLE（见接口文档 4.1）。

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from app.core import config
from app.core.deps import get_db
from app.core.envelope import ok
from app.core.errors import ApiError, ErrorCode
from app.core.time_utils import to_api_time, utc_now

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health(request: Request, db: Annotated[DbSession, Depends(get_db)]) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ApiError(
            503,
            ErrorCode.DATABASE_UNAVAILABLE,
            "数据库不可用",
            {"reason": type(exc).__name__},
        ) from exc

    return ok(
        request,
        {
            "status": "ok",
            "database": "ok",
            "model_provider": config.model_provider_name(),
            "version": config.APP_VERSION,
            "server_time": to_api_time(utc_now()),
        },
    )
