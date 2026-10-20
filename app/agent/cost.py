"""模型调用成本与延迟日志（EVA-03）。

Agent 层不查库，这里用进程内列表 + 结构化日志记录每次模型调用的
路由、模型名、模式、耗时、token、错误与降级状态。后端可在请求结束后
从 get_call_logs() 读取并落库到 AIAnalysis 表。

session_id 通过 contextvar 注入：run_copilot / extract_promises 在入口设置，
所有嵌套调用自动带上当前会话，用于按会话统计成本。
"""

import contextvars
import json
import logging
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger("app.agent.cost")

_current_session: contextvars.ContextVar[str | None] = contextvars.ContextVar("cost_session_id", default=None)

# 模型单价表（¥ / 每百万 token）。用于把 token 用量折算为可展示的「应用成本」。
# 取值参考官方公开定价，演示用；换模型时在 .env 调整 MODEL_* 并同步此处即可。
MODEL_PRICING: dict[str, dict[str, float]] = {
    "deepseek-chat": {"input": 1.0, "output": 2.0},
    "deepseek-reasoner": {"input": 4.0, "output": 16.0},
    "deepseek-flash": {"input": 1.0, "output": 2.0},  # 视作 deepseek-chat 档
    "qwen-plus": {"input": 0.8, "output": 2.0},
    "qwen-turbo": {"input": 0.3, "output": 0.6},
    "default": {"input": 1.0, "output": 2.0},
}


def model_price(model: str) -> dict[str, float]:
    return MODEL_PRICING.get(model) or MODEL_PRICING["default"]


def compute_cost_yuan(model: str, input_tokens: int, output_tokens: int) -> float:
    """按模型单价把 token 折算成 ¥（精确浮点，保留小额精度）。降级/Mock 调用不计费。"""
    price = model_price(model)
    cost = (input_tokens / 1_000_000) * price["input"] + (output_tokens / 1_000_000) * price["output"]
    return round(cost, 6)


def format_yuan(cost_yuan: float) -> str:
    """¥ 字符串，保留 4 位小数以体现「分厘级」的小额成本（如 ¥0.0020）。"""
    return f"\u00a5{cost_yuan:.4f}"


@dataclass
class ModelCallRecord:
    session_id: str | None
    route: str
    model: str
    mode: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    error: str | None
    degraded: bool
    started_at: str = ""
    cost_yuan: float = 0.0


class TokenCapture(BaseCallbackHandler):
    """在 LLM 调用结束时捕获 token 用量，供成本日志使用。"""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            first = response.generations[0][0]
            message = getattr(first, "message", None)
            if message is None:
                return
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                usage = (getattr(message, "response_metadata", None) or {}).get("token_usage")
            if not usage:
                return
            self.input_tokens = int(usage.get("input_tokens") or 0)
            self.output_tokens = int(usage.get("output_tokens") or 0)
            self.total_tokens = int(usage.get("total_tokens") or (self.input_tokens + self.output_tokens))
        except Exception:
            # token 统计失败不阻断主流程，成本日志只是观测
            return


_records: list[ModelCallRecord] = []
_lock = threading.Lock()


def set_session(session_id: str | None) -> None:
    _current_session.set(session_id)


def record_call(
    *,
    route: str,
    model: str,
    mode: str,
    latency_ms: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    error: str | None = None,
    degraded: bool = False,
    session_id: str | None = None,
) -> None:
    """记录一次模型调用（含 Mock / 降级调用，token 为 0）。

    session_id 可显式传入以覆盖 contextvar：LangGraph 在异步图中执行同步节点时
    可能丢 contextvar，由节点从 state 显式带参更稳；缺省时回退到 contextvar。
    """
    sid = session_id if session_id is not None else _current_session.get()
    cost_yuan = 0.0 if degraded else compute_cost_yuan(model, input_tokens, output_tokens)
    rec = ModelCallRecord(
        session_id=sid,
        route=route,
        model=model,
        mode=mode,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        error=error,
        degraded=degraded,
        started_at=datetime.now(UTC).isoformat(),
        cost_yuan=cost_yuan,
    )
    with _lock:
        _records.append(rec)
    logger.info("model_call %s", json.dumps(asdict(rec), ensure_ascii=False))


def get_call_logs() -> list[ModelCallRecord]:
    with _lock:
        return list(_records)


def clear_call_logs() -> None:
    with _lock:
        _records.clear()


def session_totals(session_id: str) -> dict[str, int | float | str]:
    """按会话聚合：总调用数、总 token、总耗时、总成本（¥ 数值 + 展示串）。"""
    calls = [r for r in get_call_logs() if r.session_id == session_id]
    cost = sum(r.cost_yuan for r in calls)
    return {
        "calls": len(calls),
        "input_tokens": sum(r.input_tokens for r in calls),
        "output_tokens": sum(r.output_tokens for r in calls),
        "total_tokens": sum(r.total_tokens for r in calls),
        "latency_ms": sum(r.latency_ms for r in calls),
        "cost_yuan": cost,  # 数值型 ¥，便于前端直接格式化
        "cost_yuan_display": format_yuan(cost),
        "cost_cent": int(round(cost * 100)),
        "degraded": sum(1 for r in calls if r.degraded),
    }


def rollup(session_ids: list[str]) -> dict[str, int | float | str]:
    """跨多个会话聚合（用于「一个用户所有对话」的成本汇总）。"""
    ids = set(session_ids)
    calls = [r for r in get_call_logs() if r.session_id in ids]
    cost = sum(r.cost_yuan for r in calls)
    return {
        "sessions": len({r.session_id for r in calls}),
        "calls": len(calls),
        "input_tokens": sum(r.input_tokens for r in calls),
        "output_tokens": sum(r.output_tokens for r in calls),
        "total_tokens": sum(r.total_tokens for r in calls),
        "latency_ms": sum(r.latency_ms for r in calls),
        "cost_yuan": cost,  # 数值型 ¥
        "cost_yuan_display": format_yuan(cost),
        "cost_cent": int(round(cost * 100)),
        "degraded": sum(1 for r in calls if r.degraded),
    }
