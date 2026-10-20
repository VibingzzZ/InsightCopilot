"""WebSocket 连接管理与状态广播（实时同步）。

极简实现：进程内按 session_id 维护活动连接。测试 API 触发的分析结果通过
broadcast 实时推送给前端 WS 客户端，保证前后端数据同步。

多副本 / 多进程部署时需换成 Redis 发布订阅，但单机本地联调与 Demo 足够。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """按 session 维护 WebSocket 连接，支持单播（send）与广播（broadcast）。"""

    def __init__(self) -> None:
        # session_id -> 该会话下的所有活动连接
        self._conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns[session_id].add(ws)
        logger.info("ws connected session=%s active=%d", session_id, len(self._conns[session_id]))

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        self._conns[session_id].discard(ws)
        if not self._conns[session_id]:
            self._conns.pop(session_id, None)

    async def send(self, ws: WebSocket, message: dict[str, Any]) -> None:
        """单播：把一条消息发给指定连接。"""
        await ws.send_json(message)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        """广播：把消息推给该 session 的所有连接。

        没有连接时静默丢弃，不阻断触发方主流程；个别连接异常则清理后继续。
        """
        dead: list[WebSocket] = []
        for ws in list(self._conns.get(session_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # 连接已断开但未触发 disconnect
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)
        if dead:
            logger.info("ws broadcast dropped %d dead conns session=%s", len(dead), session_id)


# 进程内单例：WS 路由与测试 API 共用同一份连接表
manager = ConnectionManager()
