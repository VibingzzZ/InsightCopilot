# 承诺路由：抽取、列表、扫描与状态流转
#
# 对应赛题「服务承诺跟踪」闭环：
#   POST /api/promises/extract  —— 从客服最终消息抽取并落库（仅最终发送消息生效）
#   GET  /api/promises          —— 主管履约雷达的承诺队列（按风险/状态/截止时间筛选）
#   POST /api/promises/scan     —— 即时重算 due_soon / overdue（无需真实等待）
#   PATCH /api/promises/{id}    —— 确认 / 变更 / 履约 / 取消 / 升级

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.schemas.api import PromiseExtractRequest, PromisePatch, PromiseScanRequest
from app.services import promise_service

router = APIRouter(prefix="/api/promises", tags=["promises"])


@router.get("")
def list_promises(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    status: str | None = Query(
        None, description="按状态筛选：pending_confirmation/active/due_soon/overdue/fulfilled/changed/cancelled"
    ),
    session_id: str | None = Query(None),
    consumer_id: str | None = Query(None),
    risk_level: str | None = Query(None, description="按会话风险等级筛选：L0/L1/L2/L3"),
    due_before: str | None = Query(None, description="截止时间早于该 ISO 时间"),
    overdue: bool = Query(False, description="仅返回已超时承诺"),
    limit: int = Query(200, ge=1, le=500),
) -> dict:
    items = promise_service.list_promises(
        db,
        status=status,
        session_id=session_id,
        consumer_id=consumer_id,
        risk_level=risk_level,
        due_before=due_before,
        overdue_only=overdue,
        limit=limit,
    )
    return ok(request, {"items": items, "total": len(items)})


@router.post("/extract")
def extract_promise(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    payload: PromiseExtractRequest,
    x_operator_id: str | None = Header(None, alias="X-Operator-ID"),
) -> dict:
    """从一条客服已发送消息抽取承诺。无承诺时 created=false。"""
    item = promise_service.create_promise_from_message(
        db,
        session_id=payload.session_id,
        message_id=payload.message_id,
        text=payload.message_text,
        mode=payload.mode,
    )
    return ok(request, {"created": item is not None, "promise": item})


@router.post("/scan")
def scan_promises(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    payload: PromiseScanRequest,
) -> dict:
    """即时扫描到期状态（可演示用，不依赖真实等待）。"""
    result = promise_service.scan_promises(db)
    return ok(request, result)


@router.patch("/{promise_id}")
def patch_promise(
    request: Request,
    promise_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    payload: PromisePatch,
    x_operator_id: str | None = Header(None, alias="X-Operator-ID"),
) -> dict:
    """确认 / 变更 / 履约 / 取消 / 升级单条承诺。"""
    item = promise_service.patch_promise(db, promise_id, payload, operator_id=x_operator_id)
    return ok(request, item)
