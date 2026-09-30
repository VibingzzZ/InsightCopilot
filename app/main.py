# FastAPI 应用入口：中间件、全局异常处理与路由挂载
#
# 全局约定（见接口设计文档第 2 节）：
# - 成功/失败统一封装 {data, meta, error}；Base URL 为 /api
# - 请求日志带 request_id / operator_id，不记录请求体与敏感原文
# - 模型超时/断网时业务接口仍返回 200 + degraded 结果；仅数据库不可读写才阻断

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import api_router
from app.core import config
from app.core.envelope import error_response, request_id_of
from app.core.errors import ApiError, ErrorCode
from app.core.middleware import RequestContextMiddleware

logger = logging.getLogger("app.main")

app = FastAPI(title=config.APP_NAME, version=config.APP_VERSION)

# 中间件：后添加的位于更外层；CORS 需要最外层以便直接响应预检请求
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(api_router, prefix=config.API_PREFIX)


@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status_code, request_id_of(request), exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        400,
        request_id_of(request),
        ErrorCode.INVALID_PARAMETER,
        "请求参数不合法",
        _validation_details(exc),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(exc.status_code, request_id_of(request), _code_for_status(exc.status_code), str(exc.detail))


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error request_id=%s", request_id_of(request))
    return error_response(500, request_id_of(request), ErrorCode.INTERNAL_ERROR, "服务内部错误")


def _validation_details(exc: RequestValidationError) -> dict:
    """只保留定位/类型/描述，不回显请求体原文（可能包含敏感内容）。"""
    return {
        "errors": [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in exc.errors()
        ]
    }


def _code_for_status(status_code: int) -> str:
    if status_code == 404:
        return ErrorCode.NOT_FOUND
    if status_code == 405:
        return ErrorCode.METHOD_NOT_ALLOWED
    if status_code == 401:
        return ErrorCode.UNAUTHORIZED
    if status_code == 403:
        return ErrorCode.FORBIDDEN
    if status_code < 500:
        return ErrorCode.INVALID_PARAMETER
    return ErrorCode.INTERNAL_ERROR
