"""跨会话轨迹摘要节点（AG-05）。

消费 CopilotRequest.events（后端按消费者预组装的历史事件）产出
timeline_summary，供右侧「全轨迹」与回复草稿引用历史承诺
/ 进度。
"""

from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_summary
from app.agent.schemas.analysis import TrajectorySummary
from app.agent.state import CustomerState
from app.prompt.summary import TRAJECTORY_SUMMARY_PROMPT


def summary_node(state: CustomerState) -> dict:
    events = state.get("events") or []
    tickets = state.get("tickets") or []
    promises = state.get("promises") or []

    # 降本：无历史（事件/工单/承诺均为空）时，轨迹摘要没有可压缩的信息，
    # 直接走确定性 mock，省掉一次模型调用。
    if not (events or tickets or promises):
        summary = mock_summary(
            events,
            state.get("messages") or [],
            state.get("orders") or [],
            tickets,
            promises,
        )
        return {"timeline_summary": summary.summary}

    prompt = TRAJECTORY_SUMMARY_PROMPT.format(
        message=state.get("current_message", ""),
        risk_level=state.get("risk_level", "L0"),
        events=events,
        orders=state.get("orders") or [],
        tickets=tickets,
        promises=promises,
        format_instructions=format_instructions(TrajectorySummary),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=TrajectorySummary,
        route="reasoning",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_summary(
            state.get("events") or [],
            state.get("messages") or [],
            state.get("orders") or [],
            state.get("tickets") or [],
            state.get("promises") or [],
        ),
        session_id=state.get("session_id"),
    )

    return {"timeline_summary": result.summary, "degraded": degraded}
