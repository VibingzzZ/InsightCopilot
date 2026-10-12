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
# 注意：本项目当前只接入了 DeepSeek。fast 路由原默认指向百炼(DashScope)，但 .env 中
# DASHSCOPE_API_KEY 仅为占位符，会导致 intent/emotion/rewrite 节点全部降级 Mock。
# 故将 fast 也指向 DeepSeek（deepseek-flash 即快模型），全链路统一走 ds。
# 若后续接入百炼，把此行改回 MODEL_FAST/DASHSCOPE_* 即可。
ROUTE_ENV: dict[str, tuple[str, str, str]] = {
    "fast": ("MODEL_DS", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
    "reasoning": ("MODEL_REASONING", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
    "vision": ("MODEL_VISION", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"),
}

# 兼容旧命名：早期用 MODEL_DS 指代推理模型
_LEGACY_MODEL_ENV: dict[str, str] = {"reasoning": "MODEL_DS"}

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

    def _resolve_model(self, route: str) -> str:
        """返回路由实际使用的模型名；主名未配置时回退到旧命名。"""
        model_env, _, _ = self._env_names(route)
        value = os.getenv(model_env, "")
        if not value and route in _LEGACY_MODEL_ENV:
            value = os.getenv(_LEGACY_MODEL_ENV[route], "")
        return value or ""

    def model_name_for(self, route: str = DEFAULT_ROUTE) -> str:
        """只读模型名，供成本日志等观测使用，不抛异常。"""
        return self._resolve_model(route)

    def _key_usable(self, key_env: str) -> bool:
        """API Key 非空且为 ASCII 才视为可用。

        占位 Key（如中文「你的百炼key」）会导致 OpenAI 客户端在构造请求头时抛
        UnicodeEncodeError，因此显式判为非可用，强制走 Mock 降级，保持日志干净。
        """
        key = os.getenv(key_env, "")
        if not key:
            return False
        try:
            key.encode("ascii")
        except UnicodeEncodeError:
            return False
        return True

    def is_available(self, route: str = DEFAULT_ROUTE) -> bool:
        """模型名和 API Key 都配置了（且 Key 非占位）才算可用。"""
        _, key_env, _ = self._env_names(route)
        return bool(self._resolve_model(route)) and self._key_usable(key_env)

    def get(self, route: str = DEFAULT_ROUTE) -> ChatOpenAI:
        if not self.is_available(route):
            model_env, key_env, _ = self._env_names(route)
            raise ModelUnavailableError(f"模型路由 {route} 不可用：请在 .env 中同时配置 {model_env} 和 {key_env}")

        if route not in self._clients:
            _, key_env, base_url_env = self._env_names(route)
            self._clients[route] = ChatOpenAI(
                model=self._resolve_model(route),
                api_key=SecretStr(os.getenv(key_env, "")),
                base_url=os.getenv(base_url_env) or None,
                temperature=self.temperature,
                # 关键：显式超时，避免网络抖动/代理拦截时无限挂起（此前 MODEL_TIMEOUT_SECONDS
                # 定义了却没接进来，导致调用卡死、整条分析链路“一直转”）。
                timeout=float(os.getenv("MODEL_TIMEOUT_SECONDS", "20")),
                max_retries=int(os.getenv("MODEL_MAX_RETRIES", "1")),
            )

        return self._clients[route]


gateway = ModelGateway()
