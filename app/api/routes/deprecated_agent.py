# 【已下线】Agent 副驾结论与 SSE 事件流路由——当前开发阶段仅保留核心数据查询与管理 API。
#
# 下线原因：本阶段聚焦客户/会话/消息/订单/工单基础接口，副驾结论与实时推送不参与联调。
# 恢复方式：在 app/api/routes/__init__.py 重新 include_router(deprecated_agent.router)。
# 依赖模块（app/agents/copilot.py、app/core/events.py）均保留完好，可直接恢复挂载。

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app.agents import copilot
from app.core import config
from app.core.deps import get_db
from app.core.envelope import ok, request_id_of
from app.core.errors import session_not_found
from app.core.events import event_bus
from app.models import ServiceSession

router = APIRouter(prefix="/api/sessions", tags=["deprecated-agent"])


@router.get("/{session_id}/copilot")
def get_session_copilot(
    request: Request,
    session_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    mode: Literal["auto", "fast", "reasoning", "vision", "mock"] = Query("auto"),
    refresh: bool = Query(False, description="true 时强制重新生成，忽略缓存"),
) -> dict:
    """触发或读取当前会话的 Agent 结论（不改变业务状态）。"""
    outcome = copilot.generate_copilot(db, session_id, mode=mode, refresh=refresh, request_id=request_id_of(request))
    return ok(
        request,
        {
            "insight": outcome.insight,
            "draft_reply": outcome.draft_reply,
            "generated_at": outcome.generated_at,
            "analysis_id": outcome.analysis_id,
            "evidence": outcome.insight.get("evidence", []),
            "model_route": outcome.model_route,
            "degraded": outcome.degraded,
        },
    )


@router.get("/{session_id}/stream")
async def stream_session_events(
    request: Request,
    session_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """SSE 推送 Agent 生成、动作执行与承诺状态变化；断线可用 Last-Event-ID 重连。"""
    if db.get(ServiceSession, session_id) is None:
        raise session_not_found(session_id)
    return StreamingResponse(
        _event_stream(session_id, last_event_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


async def _event_stream(session_id: str, last_event_id: str | None) -> AsyncIterator[str]:
    yield ": connected\n\n"
    for record in event_bus.replay_after(session_id, last_event_id):
        yield _format_sse(record)
    subscription = event_bus.register(session_id)
    try:
        while True:
            try:
                record = await asyncio.wait_for(subscription.queue.get(), timeout=config.SSE_KEEPALIVE_SECONDS)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield _format_sse(record)
    finally:
        event_bus.unregister(session_id, subscription)


def _format_sse(record: dict[str, Any]) -> str:
    data = json.dumps(record["data"], ensure_ascii=False)
    return f"id: {record['id']}\nevent: {record['event']}\ndata: {data}\n\n"
