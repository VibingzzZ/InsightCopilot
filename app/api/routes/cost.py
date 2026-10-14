# 成本可观测接口（赛题加分项：模型性能与成本优化能力）
#
# 暴露 Agent 层的 token / 调用统计与折算金额，用于量化「成本节约机制」的实际效果：
#   GET /api/cost/summary              —— 全局汇总 + 按路由聚合（可对比合并前后）
#   GET /api/cost/{session_id}         —— 单会话明细（含每次调用的 route/model/token/degraded/成本）
#   GET /api/cost/consumer/{consumer_id} —— 单用户汇总（一个用户所有会话的成本合并）
#
# 数据源：app/agent/cost.py 的进程内调用日志。入口（run_copilot / WS）会注入 session_id。

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.agent import cost
from app.core.deps import get_db
from app.core.envelope import ok
from app.models.models import ServiceSession

router = APIRouter(tags=["cost"])


@router.get("/api/cost/summary")
def cost_summary(request: Request) -> dict:
    """全局成本汇总：总调用数、真实/Mock 调用数、总 token 与总成本，以及按路由的拆分。"""
    logs = cost.get_call_logs()

    by_route: dict[str, dict] = {}
    for rec in logs:
        agg = by_route.setdefault(
            rec.route,
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "degraded": 0, "cost_yuan": 0.0},
        )
        agg["calls"] += 1
        agg["input_tokens"] += rec.input_tokens
        agg["output_tokens"] += rec.output_tokens
        agg["total_tokens"] += rec.total_tokens
        agg["degraded"] += int(rec.degraded)
        agg["cost_yuan"] += rec.cost_yuan

    return ok(
        request,
        {
            "total_calls": len(logs),
            "real_calls": sum(1 for r in logs if not r.degraded),
            "mock_calls": sum(1 for r in logs if r.degraded),
            "total_tokens": sum(r.total_tokens for r in logs),
            "total_latency_ms": sum(r.latency_ms for r in logs),
            "total_cost_yuan": cost.format_yuan(sum(r.cost_yuan for r in logs)),
            "by_route": by_route,
        },
    )


@router.get("/api/cost/{session_id}")
def cost_session(request: Request, session_id: str) -> dict:
    """单会话成本明细：聚合值 + 每次模型调用的明细，便于逐条核对 token 与成本。"""
    logs = [r for r in cost.get_call_logs() if r.session_id == session_id]
    return ok(
        request,
        {
            "session_id": session_id,
            "totals": cost.session_totals(session_id),
            "calls": [asdict(r) for r in logs],
        },
    )


@router.get("/api/cost/consumer/{consumer_id}")
def cost_consumer(
    request: Request,
    consumer_id: str,
    db: Annotated[DbSession, Depends(get_db)],
) -> dict:
    """单用户成本汇总：把一个消费者名下所有会话的 AI 成本合并（一个用户所有对话）。"""
    session_ids = list(
        db.scalars(select(ServiceSession.session_id).where(ServiceSession.consumer_id == consumer_id)).all()
    )
    return ok(
        request,
        {
            "consumer_id": consumer_id,
            "session_count": len(session_ids),
            "session_ids": session_ids,
            "totals": cost.rollup(session_ids),
        },
    )
