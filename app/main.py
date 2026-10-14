# FastAPI 应用入口：中间件、全局异常处理与路由挂载
#
# 全局约定（见接口设计文档第 2 节）：
# - 成功/失败统一封装 {data, meta, error}；Base URL 为 /api
# - 请求日志带 request_id / operator_id，不记录请求体与敏感原文
# - 模型超时/断网时业务接口仍返回 200 + degraded 结果；仅数据库不可读写才阻断

import asyncio
import json
import logging

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import api_router
from app.agent import cost
from app.agent.rewrite import rewrite_draft
from app.agent.run import run_copilot
from app.agent.schemas.contract import AgentMode, CopilotRequest
from app.core import config
from app.core.envelope import error_response, request_id_of
from app.core.errors import ApiError, ErrorCode
from app.core.middleware import RequestContextMiddleware
from app.realtime.connection import manager
from app.schemas.commands import CommandError, parse_command

logger = logging.getLogger("app.main")

# 关键修复：不要在启动时立刻导入 LangGraph
# 这样 CI / import smoke test 在没有 API Key 时也不会直接崩掉。
try:
    from app.agent.graph import graph
except Exception:
    logger.warning("Agent graph unavailable at startup; it will be initialized lazily.", exc_info=True)
    graph = None


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

# 路由自身已带 /api 前缀（如 /api/sessions、/api/health），这里不再叠加 prefix，
# 否则会变成 /api/api/* 导致 404。
app.include_router(api_router)

# 上传文件静态服务：/media/<file> 直接返回 data/media/ 下的文件（对应 /api/uploads 上传接口）。
# 目录由 config 在导入阶段创建，StaticFiles 挂载要求其已存在。
app.mount(config.UPLOAD_URL_PREFIX, StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")


# 测试接口（任务 04）：模拟买家消息，跑一次副驾分析并实时广播给 WS 客户端。
# 仅用于本地联调与验证，不落库、不影响业务状态。
class BuyerMessageIn(BaseModel):
    session_id: str = "S-TEST"
    message: str
    customer_name_masked: str | None = None
    mode: AgentMode = "auto"


class BuyerMessageOut(BaseModel):
    session_id: str
    result: dict


@app.post("/api/test/buyer_message", response_model=BuyerMessageOut)
async def simulate_buyer_message(payload: BuyerMessageIn) -> BuyerMessageOut:
    """模拟买家发送消息，触发一次副驾分析并实时广播给 WS 客户端。"""
    req = CopilotRequest(
        session_id=payload.session_id,
        customer_name_masked=payload.customer_name_masked,
        current_message=payload.message,
        messages=[
            {
                "message_id": "M-TEST",
                "sender_type": "customer",
                "message_text": payload.message,
                "content_type": "text",
            }
        ],
        mode=payload.mode,
    )

    # 副驾链路是同步的，放到线程池避免阻塞事件循环。
    result = await run_in_threadpool(run_copilot, req)

    # 广播分析结果，保持前端与后端同步（无连接时静默丢弃，任务 05）。
    await manager.broadcast(
        payload.session_id,
        {"type": "analysis", "session_id": payload.session_id, "result": result.model_dump()},
    )

    return BuyerMessageOut(session_id=payload.session_id, result=result.model_dump())


@app.get("/health")
async def health() -> dict:
    """健康检查（向后兼容：原独立 main.py 与联调脚本均依赖此端点）。"""
    return {"status": "ok"}


def _get_graph():
    """懒加载 LangGraph，避免 import 时间崩掉。"""
    global graph
    if graph is None:
        from app.agent.graph import graph as lazy_graph

        graph = lazy_graph
    return graph


# WebSocket 路由（保留本地的 Chat Stream 逻辑）
# WebSocket 路由：保留原有「买家消息 → LangGraph 流式分析」逻辑，并升级支持
# 结构化功能指令（adjust_tone 等，任务 01/03）；同时把连接登记到 ConnectionManager，
# 以接收测试接口的分析广播（任务 05）。
@app.websocket("/api/chat/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    g = _get_graph()
    await manager.connect(session_id, websocket)  # 接受连接并登记，供广播使用
    print(f"[WebSocket] Connected: {session_id}")
    # 成本观测：在连接级注入 session_id，覆盖「对话流」与「轻量改写指令」两条路径
    cost.set_session(session_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                await manager.send(websocket, {"type": "error", "code": "BAD_JSON", "message": "消息需为合法 JSON"})
                continue

            # 任务 01/03：结构化功能指令（adjust_tone 等）→ 轻量改写，绕过重流程
            if isinstance(payload, dict) and payload.get("command"):
                try:
                    cmd = parse_command(payload)
                except CommandError as exc:
                    await manager.send(websocket, {"type": "error", "code": exc.code, "message": exc.message})
                    continue
                out = rewrite_draft(cmd=cmd, mode="auto")
                await manager.send(
                    websocket,
                    {
                        "type": "rewrite",
                        "command": cmd.command.value,
                        "params": cmd.params,
                        "rewritten": out["rewritten"],
                        "degraded": out["degraded"],
                        "model_route": out["model_route"],
                    },
                )
                continue

            # 原有 chat stream 行为（向后兼容）
            text = payload.get("text", "") if isinstance(payload, dict) else str(payload)
            print(f"[WebSocket] Received from {session_id}: {text}")

            # 构造 LangGraph 初始状态，使用 mock mode 防止没有配置 API key 时崩溃
            initial_state = {
                "session_id": session_id,
                "customer_name_masked": "消费者",
                "current_message": text,
                "messages": [{"role": "buyer", "text": text}],
                "orders": [{"id": "ORD-DEMO", "item": "测试商品"}],
                "tickets": [],
                "promises": [],
                "events": [],
                "mode": "auto",  # 已配 DeepSeek 时走真实分析；无 Key/调用失败自动降级 Mock（不再强制 mock）
            }

            await websocket.send_json({"type": "start"})

            try:
                # 迭代 LangGraph
                async for event in g.astream(initial_state, stream_mode="updates"):
                    for node_name, node_state in event.items():
                        print(f"--- Node: {node_name} ---")
                        await websocket.send_json(
                            {
                                "type": "node_update",
                                "node": node_name,
                                "data": jsonable_encoder(node_state),
                            }
                        )
                        await asyncio.sleep(0.5)
            finally:
                # 会话流结束：把本会话（及该用户累计）的 AI 消耗折算后回传 + 落日志，
                # 满足赛题「能看到 AI 应用成本」与「降本机制可量化」的加分项。
                totals = cost.session_totals(session_id)
                logger.info("cost_summary session=%s %s", session_id, json.dumps(totals, ensure_ascii=False))
                await websocket.send_json(
                    {"type": "cost_summary", "session_id": session_id, "totals": totals}
                )

            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected: {session_id}")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        cost.set_session(None)
        manager.disconnect(session_id, websocket)


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
    return error_response(
        exc.status_code,
        request_id_of(request),
        _code_for_status(exc.status_code),
        str(exc.detail),
    )


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


if __name__ == "__main__":
    import uvicorn

    # 直接 `python app/main.py` 即可启动；reload 在 Windows 下易起子进程，Demo 场景关闭。
    uvicorn.run(app, host="127.0.0.1", port=8000)
