import logging
import time
from collections.abc import Callable
from typing import TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

from app.agent import cost
from app.integrations.model.gateway import ModelUnavailableError, gateway

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
_PARSERS: dict[type[BaseModel], PydanticOutputParser] = {}


def parser_for[T: BaseModel](schema: type[T]) -> PydanticOutputParser:
    """PydanticOutputParser 可复用，缓存避免每次重建。"""
    if schema not in _PARSERS:
        _PARSERS[schema] = PydanticOutputParser(pydantic_object=schema)
    return _PARSERS[schema]


def format_instructions[T: BaseModel](schema: type[T]) -> str:
    """节点构造 prompt 时用它拿 JSON 格式说明。"""
    return parser_for(schema).get_format_instructions()


def run_structured[T: BaseModel](
    *,
    prompt: str,
    schema: type[T],
    route: str,
    mode: str,
    fallback: Callable[[], T],
) -> tuple[T, bool]:
    """按路由调用模型；返回 (结构化结果, 是否降级)。

    mode 语义：
      mock  —— 永远用 fallback
      auto  —— 有配置就走模型，无配置或调用失败都降级到 fallback
      real  —— 强制走模型，缺配置或失败直接抛异常（仅开发/评测用）
    """
    model = gateway.model_name_for(route)

    if mode == "mock":
        cost.record_call(route=route, model="", mode=mode, latency_ms=0, degraded=True)
        return fallback(), True

    if not gateway.is_available(route):
        if mode == "real":
            raise ModelUnavailableError(f"mode=real 但路由 {route} 未配置模型，无法执行")
        logger.warning("模型路由 %s 不可用，降级到 Mock 结果", route)
        cost.record_call(route=route, model=model, mode=mode, latency_ms=0, error="route unavailable", degraded=True)
        return fallback(), True

    parser = parser_for(schema)
    chain = gateway.get(route).bind(response_format={"type": "json_object"}) | parser
    token_capture = cost.TokenCapture()
    started = time.monotonic()
    try:
        result = chain.invoke(prompt, config={"callbacks": [token_capture]})
        latency_ms = int((time.monotonic() - started) * 1000)
        cost.record_call(
            route=route,
            model=model,
            mode=mode,
            latency_ms=latency_ms,
            input_tokens=token_capture.input_tokens,
            output_tokens=token_capture.output_tokens,
            total_tokens=token_capture.total_tokens,
        )
        return result, False
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        if mode == "real":
            raise
        logger.exception("模型调用失败，降级到 Mock 结果（route=%s）", route)
        cost.record_call(route=route, model=model, mode=mode, latency_ms=latency_ms, error=str(exc), degraded=True)
        return fallback(), True
