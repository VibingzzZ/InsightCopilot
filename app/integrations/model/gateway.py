"""模型调用网关。

设计要点：
1. 模型名称不写死在代码里，全部从 .env 读取，便于换模型和现场演示。
2. 构造客户端是惰性的：缺少 API Key 时不在 import 期抛异常，否则整个包都无法加载，
   无 Key 的离线/Mock 演示路径会被直接掐死。
3. 缺配置时抛 ModelUnavailableError，由 Agent 层捕获并降级到 Mock 结果。
"""

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

# 模型路由 -> (模型名环境变量, API Key 环境变量, Base URL 环境变量)
ROUTE_ENV: dict[str, tuple[str, str, str]] = {
    "fast": ("MODEL_FAST", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"),
    "reasoning": ("MODEL_DS", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
    "vision": ("MODEL_VISION", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"),
}

DEFAULT_ROUTE = "fast"


class ModelUnavailableError(RuntimeError):
    """模型路由不可用（缺模型名或 API Key）。调用方必须降级，不得中断链路。"""


class ModelGateway:
    """按路由惰性创建 ChatOpenAI 客户端。"""

    def __init__(self, temperature: float = 0.5) -> None:
        self.temperature = temperature
        self._clients: dict[str, ChatOpenAI] = {}

    def _env_names(self, route: str) -> tuple[str, str, str]:
        return ROUTE_ENV.get(route, ROUTE_ENV[DEFAULT_ROUTE])

    def is_available(self, route: str = DEFAULT_ROUTE) -> bool:
        """模型名和 API Key 都配置了才算可用。"""
        model_env, key_env, _ = self._env_names(route)
        return bool(os.getenv(model_env)) and bool(os.getenv(key_env))

    def get(self, route: str = DEFAULT_ROUTE) -> ChatOpenAI:
        if not self.is_available(route):
            model_env, key_env, _ = self._env_names(route)
            raise ModelUnavailableError(f"模型路由 {route} 不可用：请在 .env 中同时配置 {model_env} 和 {key_env}")

        if route not in self._clients:
            model_env, key_env, base_url_env = self._env_names(route)
            self._clients[route] = ChatOpenAI(
                model=os.getenv(model_env, ""),
                api_key=SecretStr(os.getenv(key_env, "")),
                base_url=os.getenv(base_url_env) or None,
                temperature=self.temperature,
            )

        return self._clients[route]


gateway = ModelGateway()
