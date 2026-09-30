# 请求上下文中间件：request_id 注入、访问日志、写接口简易限流
#
# - 使用纯 ASGI 实现，避免包装层破坏 SSE 流式响应。
# - 日志只记录 request_id、路由、状态码、耗时、operator_id，不记录请求体。

import logging
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from app.core import config

logger = logging.getLogger("app.request")

_HEADER_REQUEST_ID = b"x-request-id"
_HEADER_OPERATOR_ID = b"x-operator-id"
_WRITE_METHODS = {b"POST", b"PUT", b"PATCH", b"DELETE"}


class RequestContextMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app
        self._write_hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = (headers.get(_HEADER_REQUEST_ID) or b"").decode() or f"req_{uuid.uuid4().hex[:12]}"
        operator_id = (headers.get(_HEADER_OPERATOR_ID) or b"").decode() or None

        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["operator_id"] = operator_id

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        # 写接口简易限流：按 operator 或客户端地址，60 秒滑动窗口
        if method.encode() in _WRITE_METHODS and path.startswith(config.API_PREFIX):
            limited = self._check_rate_limit(scope, operator_id)
            if limited is not None:
                from app.core.envelope import error_response
                from app.core.errors import ErrorCode

                response = error_response(
                    429,
                    request_id,
                    ErrorCode.RATE_LIMITED,
                    "请求过于频繁，请稍后重试",
                )
                await response(scope, receive, send)
                return

        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                raw_headers = list(message.get("headers") or [])
                raw_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = raw_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s %.1fms request_id=%s operator_id=%s",
                method,
                path,
                status_holder["status"],
                elapsed_ms,
                request_id,
                operator_id or "-",
            )

    def _check_rate_limit(self, scope: dict, operator_id: str | None) -> bool | None:
        client = scope.get("client") or ("unknown", 0)
        key = operator_id or f"ip:{client[0]}"
        now = time.monotonic()
        hits = self._write_hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= config.WRITE_RATE_LIMIT_PER_MINUTE:
            return True
        hits.append(now)
        return None
