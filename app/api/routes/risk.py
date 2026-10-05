# 风险队列路由：主管视角的会话、工单与承诺聚合
#
# 【当前阶段已下线】未在 app/api/routes/__init__.py 挂载（聚焦核心数据查询与管理 API）。
# 恢复方式：重新 include_router(risk.router)；依赖 app/services/risk_service.py 保留完好。

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.services import risk_service

router = APIRouter(prefix="/risk-queue", tags=["risk"])


@router.get("")
def get_risk_queue(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    risk_level: Literal["L0", "L1", "L2", "L3"] | None = Query(None),
    ticket_type: str | None = Query(None, max_length=50),
    status: Literal["open", "closed", "pending"] | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    items, total = risk_service.build_risk_queue(
        db, risk_level=risk_level, ticket_type=ticket_type, status=status, page=page, page_size=page_size
    )
    return ok(request, {"items": items}, page=page, page_size=page_size, total=total)
