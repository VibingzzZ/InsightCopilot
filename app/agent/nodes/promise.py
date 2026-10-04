"""承诺抽取。

模型只负责读懂「客服答应做了什么、时间原话是什么」；
due_at 一律由 time.py 归一化，模型给的日期一律不采信。
promise_type 必须落在白名单里，否则会污染数据库字段。
"""

from typing import cast, get_args

from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_promise
from app.agent.schemas.analysis import PromiseExtraction
from app.agent.schemas.contract import (
    EvidenceRef,
    ModelRoute,
    OwnerType,
    PromiseCandidate,
    PromiseExtractRequest,
    PromiseExtractResult,
    PromiseType,
)
from app.agent.time import normalize_due
from app.integrations.model.gateway import gateway
from app.prompt.promise import PROMISE_EXTRACT_PROMPT

# 模型自由输出的字符串必须校验落在白名单里
PROMISE_TYPES: tuple[str, ...] = get_args(PromiseType)
_OWNER_TYPES: tuple[str, ...] = get_args(OwnerType)
_ROUTE: ModelRoute = "fast"


def _model_route(mode: str) -> ModelRoute:
    if mode == "mock" or not gateway.is_available(_ROUTE):
        return "mock"
    return _ROUTE


def extract_promise_candidate(req: PromiseExtractRequest) -> PromiseExtractResult:
    """从一条客服已发送消息里抽取承诺候选。不建承诺，只给候选。"""
    model_route = _model_route(req.mode)

    prompt = _build_prompt(req)
    result, degraded = run_structured(
        prompt=prompt,
        schema=PromiseExtraction,
        route=_ROUTE,
        mode=req.mode,
        fallback=lambda: mock_promise(req.message_text),
    )

    if not result.has_promise:
        return PromiseExtractResult(
            candidate=None,
            needs_confirmation=False,
            model_route=model_route,
            degraded=degraded,
        )

    # 时间归一化：模型只提供原始表达，截止时间由确定性代码算
    due_at, needs_confirmation = normalize_due(result.due_expression)

    candidate = PromiseCandidate(
        promise_type=cast(PromiseType, result.promise_type) if result.promise_type in PROMISE_TYPES else "other",
        statement=result.statement or req.message_text.strip(),
        due_expression=result.due_expression or None,
        due_at=due_at,
        owner_type=cast(OwnerType, result.owner_type) if result.owner_type in _OWNER_TYPES else "agent",
        confidence=result.confidence,
        needs_confirmation=needs_confirmation,
        evidence=[
            EvidenceRef(
                source_type="chat",
                source_id=req.message_id,
                message_id=req.message_id,
                quote=req.message_text.strip()[:50],
            )
        ],
    )

    return PromiseExtractResult(
        candidate=candidate,
        needs_confirmation=needs_confirmation,
        model_route=model_route,
        degraded=degraded,
    )


def _build_prompt(req: PromiseExtractRequest) -> str:
    return PROMISE_EXTRACT_PROMPT.format(
        message=req.message_text,
        format_instructions=format_instructions(PromiseExtraction),
    )
