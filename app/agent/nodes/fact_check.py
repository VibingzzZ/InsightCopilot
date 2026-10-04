"""回复草稿的事实校验（纯代码，不调模型）。

只做一件事：把草稿里的事实断言（金额 / 时间 / 业务状态）逐个比对证据层，
对不上的收进 unverified_claims。这样「模型虚构金额或时间」即使发生，
也会在发送前被显式暴露出来，而不是直接说给消费者。

刻意不做第二次大模型审查 —— 文档的性能目标要求普通会话不增加第二次模型调用。
"""

import re

from app.agent.state import CustomerState

# 每类断言一个正则，命中后逐个比对证据原文
_CLAIM_PATTERNS: dict[str, re.Pattern[str]] = {
    "金额": re.compile(r"\d+(?:\.\d+)?\s*(?:元|块钱|块|分)"),
    "时间点": re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*[日号]|\d{1,2}\s*[:点]\s*\d{0,2}\s*分?"),
    "时长": re.compile(r"\d+\s*(?:个?\s*工作日|个?\s*自然日|天|小时|分钟)"),
    "业务状态": re.compile(r"已发货|已签收|已退款|已到账|已补发|已换货|已取消|已关闭|处理中|待处理|已完成"),
}

# 高风险等级下，未核验的事实断言直接阻断发送
_BLOCKING_LEVELS = {"L2", "L3"}


def _evidence_text(state: CustomerState) -> str:
    return " ".join(item.quote or "" for item in state.get("evidence") or [])


def _extract_claims(draft: str) -> list[tuple[str, str]]:
    claims: list[tuple[str, str]] = []

    for label, pattern in _CLAIM_PATTERNS.items():
        for match in pattern.findall(draft):
            token = (match or "").strip()
            if token:
                claims.append((label, token))

    return claims


def fact_check_node(state: CustomerState) -> dict:
    draft = state.get("reply_draft") or ""
    evidence_text = _evidence_text(state)

    unverified = [f"{label}「{token}」" for label, token in _extract_claims(draft) if token not in evidence_text]

    return {
        "fact_check": {
            "status": "needs_review" if unverified else "pass",
            "unverified_claims": unverified,
            "blocked": bool(unverified) and state.get("risk_level") in _BLOCKING_LEVELS,
        }
    }
