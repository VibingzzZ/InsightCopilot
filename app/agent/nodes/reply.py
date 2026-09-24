"""回复草稿节点。

按 risk_level 选两套 prompt：L1 以上用「高风险处置」那套，并把 adverse 产出的
safe_reply 作为骨架传进去，避免模型在不良反应场景自由发挥。
"""

from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_reply
from app.agent.schemas.analysis import ReplyDraft
from app.agent.state import CustomerState
from app.prompt.reply import REPLY_PROMPT, REPLY_PROMPT_HIGH_RISK

_HIGH_RISK_LEVELS = {"L1", "L2", "L3"}
_NO_SKELETON = "（无处置基准话术，请只做安抚并说明会继续跟进，禁止给出诊断或用药建议）"


def _evidence_lines(state: CustomerState) -> list[str]:
    return [item.quote for item in state.get("evidence") or [] if item.quote]


def reply_node(state: CustomerState) -> dict:
    risk_level = state.get("risk_level", "L0")
    safe_reply = (state.get("adverse") or {}).get("safe_reply") or _NO_SKELETON

    template = REPLY_PROMPT_HIGH_RISK if risk_level in _HIGH_RISK_LEVELS else REPLY_PROMPT
    prompt = template.format(
        message=state.get("current_message", ""),
        intent=state.get("intent", {}),
        emotion=state.get("emotion", "unknown"),
        risk_level=risk_level,
        evidence=_evidence_lines(state) or "暂无系统可核验的事实",
        suggested_actions=state.get("suggested_actions") or [],
        safe_reply=safe_reply,
        format_instructions=format_instructions(ReplyDraft),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=ReplyDraft,
        route="reasoning",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_reply(risk_level, _evidence_lines(state)),
    )

    return {"reply_draft": result.reply, "degraded": degraded}
