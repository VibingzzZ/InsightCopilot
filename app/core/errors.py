# 统一错误码与业务异常（对应接口设计文档第 5 节）

from typing import Any


class ErrorCode:
    INVALID_PARAMETER = "INVALID_PARAMETER"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    CUSTOMER_NOT_FOUND = "CUSTOMER_NOT_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    TICKET_NOT_FOUND = "TICKET_NOT_FOUND"
    PROMISE_NOT_FOUND = "PROMISE_NOT_FOUND"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    ACTION_PREVIEW_REQUIRED = "ACTION_PREVIEW_REQUIRED"
    PROMISE_TRANSITION_INVALID = "PROMISE_TRANSITION_INVALID"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    ACTION_PAYLOAD_INVALID = "ACTION_PAYLOAD_INVALID"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    RATE_LIMITED = "RATE_LIMITED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    # 扩展错误码：履约验证失败（见接口文档 4.3 MARK_FULFILLED 证据校验）
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    # 框架级错误码（HTTP 语义；资源类 404 使用各自错误码）
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ApiError(Exception):
    """业务异常，由全局异常处理器转换为统一错误响应。"""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def session_not_found(session_id: str) -> ApiError:
    return ApiError(404, ErrorCode.SESSION_NOT_FOUND, "会话不存在", {"session_id": session_id})


def customer_not_found(customer_id: str) -> ApiError:
    return ApiError(404, ErrorCode.CUSTOMER_NOT_FOUND, "客户不存在", {"customer_id": customer_id})


def order_not_found(order_id: str) -> ApiError:
    return ApiError(404, ErrorCode.ORDER_NOT_FOUND, "订单不存在", {"order_id": order_id})


def ticket_not_found(ticket_id: str) -> ApiError:
    return ApiError(404, ErrorCode.TICKET_NOT_FOUND, "工单不存在", {"ticket_id": ticket_id})


def promise_not_found(promise_id: str) -> ApiError:
    return ApiError(404, ErrorCode.PROMISE_NOT_FOUND, "承诺不存在", {"promise_id": promise_id})
