# 动作路由：预览与确认（高影响动作需先预览再确认，带幂等键防重复建单）
#
# 对应接口文档第 7.3 节：任何改变工单/承诺状态的动作必须先 preview 再 confirm，
# confirm 携带 idempotency_key，重复提交返回同一结果，避免重复建单。

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db, optional_operator
from app.core.envelope import ok
from app.core.time_utils import to_iso, utc_now
from app.models import ActionExecution
from app.schemas.api import ActionConfirmRequest, ActionPreviewRequest, PromisePatch
from app.services import promise_service, ticket_service

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.post("/preview")
def preview_action(
    request: Request,
    payload: ActionPreviewRequest,
    db: Annotated[DbSession, Depends(get_db)],
) -> dict:
    """预览动作结果（不落库）。返回预填字段与将产生的副作用描述。"""
    effect = _describe(payload.action_type, payload.draft_payload)
    preview = {
        "action_type": payload.action_type,
        "session_id": payload.session_id,
        "source_message_id": payload.source_message_id,
        "draft_payload": payload.draft_payload,
        "effect": effect,
    }
    return ok(request, {"preview": preview, "action_id": f"act-{uuid.uuid4().hex[:12]}"})


@router.post("/confirm")
def confirm_action(
    request: Request,
    payload: ActionConfirmRequest,
    db: Annotated[DbSession, Depends(get_db)],
    x_operator_id: str | None = Header(None, alias="X-Operator-ID"),
) -> dict:
    """确认执行动作。按 idempotency_key 幂等：重复提交直接返回原结果。"""
    operator_id = x_operator_id or optional_operator(request) or "agent"

    existing = db.scalar(
        select(ActionExecution).where(ActionExecution.idempotency_key == payload.idempotency_key)
    )
    if existing is not None:
        return ok(
            request,
            {
                "idempotent": True,
                "action_id": existing.action_id,
                "result_ticket_id": existing.result_ticket_id,
                "result_promise_id": existing.result_promise_id,
            },
        )

    result = _execute(db, payload, operator_id, request)
    return ok(request, result)


def _describe(action_type: str, draft: dict) -> str:
    if action_type == "CREATE_TICKET":
        return f"将创建「{draft.get('ticket_type', '服务')}」工单（优先级 {draft.get('priority', 'normal')}）"
    if action_type == "CREATE_PROMISE":
        return f"将登记服务承诺：{draft.get('statement', '待确认事项')}"
    if action_type == "MARK_FULFILLED":
        return f"将标记承诺 {draft.get('promise_id', '')} 为已履约"
    if action_type == "ESCALATE":
        return "将升级至主管/专项团队"
    if action_type == "FOLLOW_UP":
        return "将创建回访承诺"
    if action_type == "NUDGE_TICKET":
        return f"将催办工单 {draft.get('ticket_id', '')}"
    return "将执行该动作"


def _execute(db: DbSession, payload: ActionConfirmRequest, operator_id: str, request: Request) -> dict:
    action_type = payload.action_type
    draft = payload.payload or {}
    session_id = draft.get("session_id")

    result_ticket_id = None
    result_promise_id = None

    if action_type == "CREATE_TICKET":
        ticket = ticket_service.create_ticket(
            db,
            session_id=draft["session_id"],
            ticket_type=draft["ticket_type"],
            draft_payload=draft,
            priority=draft.get("priority", "normal"),
            operator_id=operator_id,
        )
        result_ticket_id = ticket.get("ticket_no")
    elif action_type == "CREATE_PROMISE":
        promise = promise_service.create_promise_from_message(
            db,
            session_id=draft["session_id"],
            message_id=draft["source_message_id"],
            text=draft.get("statement", ""),
        )
        result_promise_id = promise.get("promise_id") if promise else None
    elif action_type == "MARK_FULFILLED":
        if draft.get("promise_id"):
            promise_service.patch_promise(db, draft["promise_id"], PromisePatch(status="fulfilled"))
            result_promise_id = draft["promise_id"]

    now_iso = to_iso(utc_now())
    action_id = f"act-{uuid.uuid4().hex[:12]}"
    db.add(
        ActionExecution(
            action_id=action_id,
            action_type=action_type,
            session_id=session_id or "",
            operator_id=operator_id,
            idempotency_key=payload.idempotency_key,
            status="confirmed",
            result_ticket_id=result_ticket_id,
            result_promise_id=result_promise_id,
            request_id=getattr(request.state, "request_id", "req_unknown"),
            confirmed_at=now_iso,
            executed_at=now_iso,
        )
    )
    db.commit()
    return {
        "idempotent": False,
        "action_id": action_id,
        "result_ticket_id": result_ticket_id,
        "result_promise_id": result_promise_id,
    }
