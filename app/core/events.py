# 进程内事件总线：支撑 SSE 推送（分析、动作、承诺状态变化）
#
# 【当前阶段已下线】仅 Agent 副驾/SSE 使用，路由未挂载；代码保留待恢复。
# Demo 阶段单进程运行，使用内存缓冲 + asyncio 队列：
# - 每个会话保留最近 N 条事件，支持前端按 Last-Event-ID 断线重连补发。
# - publish 可能发生在同步路由的线程池中，订阅者按登记的事件循环跨线程投递。

import asyncio
from collections import defaultdict, deque
from typing import Any, NamedTuple

_MAX_BUFFER_PER_SESSION = 100


class Subscription(NamedTuple):
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue


class SessionEventBus:
    def __init__(self) -> None:
        self._buffers: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_BUFFER_PER_SESSION))
        self._seq: dict[str, int] = defaultdict(int)
        self._subscribers: dict[str, list[Subscription]] = defaultdict(list)

    def publish(self, session_id: str, event: str, data: dict[str, Any]) -> dict[str, Any]:
        """发布事件：event 形如 analysis.started / promise.updated。"""
        self._seq[session_id] += 1
        record = {"id": str(self._seq[session_id]), "event": event, "data": {"session_id": session_id, **data}}
        self._buffers[session_id].append(record)
        try:
            running_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None
        for subscription in self._subscribers.get(session_id, []):
            if running_loop is subscription.loop:
                subscription.queue.put_nowait(record)
            else:
                subscription.loop.call_soon_threadsafe(subscription.queue.put_nowait, record)
        return record

    def register(self, session_id: str) -> Subscription:
        """登记订阅（须在事件循环内调用）；调用方负责 unregister。"""
        subscription = Subscription(loop=asyncio.get_running_loop(), queue=asyncio.Queue())
        self._subscribers[session_id].append(subscription)
        return subscription

    def unregister(self, session_id: str, subscription: Subscription) -> None:
        subscribers = self._subscribers.get(session_id)
        if not subscribers:
            return
        if subscription in subscribers:
            subscribers.remove(subscription)
        if not subscribers:
            self._subscribers.pop(session_id, None)

    def replay_after(self, session_id: str, last_event_id: str | None) -> list[dict[str, Any]]:
        """按 Last-Event-ID 返回未送达的事件。"""
        if not last_event_id:
            return []
        try:
            last_id = int(last_event_id)
        except ValueError:
            return []
        return [rec for rec in self._buffers.get(session_id, []) if int(rec["id"]) > last_id]


# 全局单例
event_bus = SessionEventBus()
