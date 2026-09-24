import logging
from collections.abc import Callable
from typing import TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

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
    if mode == "mock":
        return fallback(), True

    if not gateway.is_available(route):
        if mode == "real":
            raise ModelUnavailableError(f"mode=real 但路由 {route} 未配置模型，无法执行")
        logger.warning("模型路由 %s 不可用，降级到 Mock 结果", route)
        return fallback(), True

    parser = parser_for(schema)
    chain = gateway.get(route).bind(response_format={"type": "json_object"}) | parser
    try:
        return chain.invoke(prompt), False
    except Exception:
        if mode == "real":
            raise
        logger.exception("模型调用失败，降级到 Mock 结果（route=%s）", route)
        return fallback(), True
