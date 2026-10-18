# Demo 重置路由：一键恢复基线演示数据（工程验收 §9.3）
#
# POST /api/demo/reset —— 清理演示运行数据并恢复 baseline-v1 固定状态，3 秒内可完成。

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.db import seed
from app.schemas.api import DemoResetRequest

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset_demo(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    payload: DemoResetRequest,
) -> dict:
    """恢复固定演示初始状态。"""
    result = seed.reset_demo(
        db,
        scenario=payload.scenario,
        preserve_import=payload.preserve_import,
    )
    db.commit()
    return ok(request, result)
