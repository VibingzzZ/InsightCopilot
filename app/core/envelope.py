# 统一响应封装：{data, meta, error}
#
# 成功：{"data": ..., "meta": {"request_id": ..., "page": ..., "total": ...}, "error": null}
# 失败：{"data": null, "meta": {"request_id": ...}, "error": {"code": ..., "message": ..., "details": {}}}

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def ok(
    request: Request,
    data: Any,
    *,
    page: int | None = None,
    page_size: int | None = None,
    total: int | None = None,
    meta_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造成功响应体（由路由直接返回，FastAPI 序列化为 JSON）。"""
    meta: dict[str, Any] = {"request_id": request_id_of(request)}
    if total is not None:
        meta["page"] = page
        meta["page_size"] = page_size
        meta["total"] = total
    if meta_extra:
        meta.update(meta_extra)
    return {"data": data, "meta": meta, "error": None}


def error_body(
    request_id: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "data": None,
        "meta": {"request_id": request_id},
        "error": {"code": code, "message": message, "details": details or {}},
    }


def error_response(
    status_code: int,
    request_id: str,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_body(request_id, code, message, details),
    )
