# 成本可观测接口（赛题加分项：模型性能与成本优化能力）
#
# 暴露 Agent 层的 token / 调用统计，用于量化「成本节约机制」的实际效果：
#   GET /api/cost/summary        —— 全局汇总 + 按路由聚合（可对比合并前后）
#   GET /api/cost/{session_id}   —— 单会话明细（含每次调用的 route/model/token/degraded）
#
# 数据源：app/agent/cost.py 的进程内调用日志。入口（run_copilot / WS）会注入 session_id。

from dataclasses import asdict

from fastapi import APIRouter, Request

from app.agent import cost
from app.core.envelope import ok

router = APIRouter(tags=["cost"])


@router.get("/api/cost/summary")
def cost_summary(request: Request) -> dict:
    """全局成本汇总：总调用数、真实/Mock 调用数、总 token，以及按路由的拆分。"""
    logs = cost.get_call_logs()

    by_route: dict[str, dict] = {}
    for rec in logs:
        agg = by_route.setdefault(
            rec.route,
            {"calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "degraded": 0},
        )
        agg["calls"] += 1
        agg["input_tokens"] += rec.input_tokens
        agg["output_tokens"] += rec.output_tokens
        agg["total_tokens"] += rec.total_tokens
        agg["degraded"] += int(rec.degraded)

    return ok(
        request,
        {
            "total_calls": len(logs),
            "real_calls": sum(1 for r in logs if not r.degraded),
            "mock_calls": sum(1 for r in logs if r.degraded),
            "total_tokens": sum(r.total_tokens for r in logs),
            "total_latency_ms": sum(r.latency_ms for r in logs),
            "by_route": by_route,
        },
    )


@router.get("/api/cost/{session_id}")
def cost_session(request: Request, session_id: str) -> dict:
    """单会话成本明细：聚合值 + 每次模型调用的明细，便于逐条核对 token。"""
    logs = [r for r in cost.get_call_logs() if r.session_id == session_id]
    return ok(
        request,
        {
            "session_id": session_id,
            "totals": cost.session_totals(session_id),
            "calls": [asdict(r) for r in logs],
        },
    )
