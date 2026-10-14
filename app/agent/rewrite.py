"""轻量草稿改写链路（Task 03）。

绕过原副驾的「查单 / 风险判定 / 证据汇总 / 事实校验」等重流程，直接针对已有
草稿做局部改写，显著降低延迟与 token 消耗。无模型配置时走确定性 Mock 降级。
"""

from __future__ import annotations

from app.agent.llm import run_structured
from app.agent.mock import mock_rewrite
from app.agent.schemas.analysis import RewriteResult
from app.prompt.rewrite import REWRITE_GOALS, REWRITE_PROMPT, TONE_GUIDE
from app.schemas.commands import FunctionCommand


def _extra_for(cmd: FunctionCommand) -> str:
    """按指令拼装额外的改写约束，保持 prompt 精炼。"""
    if cmd.command.value == "adjust_tone":
        tone = (cmd.params or {}).get("tone", "polite")
        return "语气风格：" + TONE_GUIDE.get(tone, TONE_GUIDE["polite"])
    return ""


def rewrite_draft(*, cmd: FunctionCommand, mode: str = "auto") -> dict:
    """对已有草稿做轻量改写。

    返回：
        {
            "rewritten": str,        # 改写后的草稿全文
            "degraded": bool,        # 是否走 Mock 降级
            "model_route": str,      # 实际模型路由（mock / fast）
        }
    """
    goal = REWRITE_GOALS.get(cmd.command.value, REWRITE_GOALS["optimize_expression"])
    extra = _extra_for(cmd)
    prompt = REWRITE_PROMPT.format(goal=goal, extra=extra, draft=cmd.draft)

    # 轻量任务走 fast 路由；复用 run_structured 的 JSON 解析 + 成本记录 + 降级。
    result, degraded = run_structured(
        prompt=prompt,
        schema=RewriteResult,
        route="fast",
        mode=mode,
        fallback=lambda: mock_rewrite(cmd.command.value, cmd.draft, cmd.params),
    )

    return {
        "rewritten": result.rewritten,
        "degraded": degraded,
        "model_route": "mock" if degraded else "fast",
    }
