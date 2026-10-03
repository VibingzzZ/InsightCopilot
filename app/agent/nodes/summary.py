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
    prompt = TRAJECTORY_SUMMARY_PROMPT.format(
        message=state.get("current_message", ""),
        risk_level=state.get("risk_level", "L0"),
        events=state.get("events") or [],
        orders=state.get("orders") or [],
        tickets=state.get("tickets") or [],
        promises=state.get("promises") or [],
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
    )

    return {"timeline_summary": result.summary, "degraded": degraded}
