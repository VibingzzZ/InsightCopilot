# 运行时配置：环境变量读取与 Demo 常量
#
# 百炼（DashScope）环境变量约定（见开发文档 2.3 节）：
#   DASHSCOPE_API_KEY   必填，缺失时自动降级为 Mock 路由
#   DASHSCOPE_BASE_URL  可选，默认 OpenAI 兼容模式地址
#   MODEL_FAST / MODEL_REASONING / MODEL_VISION  可选，模型名不写死在代码中

import os
from pathlib import Path

# ---------------------------------------------------------------- 基础信息

APP_NAME = "知微客服副驾"
APP_VERSION = "0.1.0"
API_PREFIX = "/api"

# 运行环境：development / test / production
APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

# 项目根目录（app/core/config.py -> 项目根）
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- .env 加载
# 标准库实现的极简 .env 读取，避免引入 python-dotenv 依赖。


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------- 模型网关

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").strip()
MODEL_FAST = os.environ.get("MODEL_FAST", "").strip()
MODEL_REASONING = os.environ.get("MODEL_REASONING", "").strip()
MODEL_VISION = os.environ.get("MODEL_VISION", "").strip()
MODEL_EMBEDDING = os.environ.get("MODEL_EMBEDDING", "").strip()

MODEL_TIMEOUT_SECONDS = float(os.environ.get("MODEL_TIMEOUT_SECONDS", "20"))
MODEL_MAX_RETRIES = 1  # JSON 解析失败时仅重试当前节点一次


def model_provider_name() -> str:
    """当前模型网关对外展示的名称。"""
    return "bailian" if DASHSCOPE_API_KEY else "mock"


def route_model_name(route: str) -> str:
    """按路由返回配置的模型名，未配置返回空字符串。"""
    return {
        "fast": MODEL_FAST,
        "reasoning": MODEL_REASONING,
        "vision": MODEL_VISION,
    }.get(route, "")


# ---------------------------------------------------------------- 业务常量

# 承诺履约雷达
PROMISE_DUE_SOON_HOURS = float(os.environ.get("PROMISE_DUE_SOON_HOURS", "24"))

# 动作预览有效期（分钟）
ACTION_PREVIEW_TTL_MINUTES = int(os.environ.get("ACTION_PREVIEW_TTL_MINUTES", "10"))

# 节假日日历（Demo 阶段使用常量配置，后续迁移到配置表）
# 仅影响“N 个工作日”计算，周六/周日自动跳过。
HOLIDAYS: set[str] = {d.strip() for d in os.environ.get("APP_HOLIDAYS", "").split(",") if d.strip()}

# 客户端伪造 now 仅允许在非生产环境使用（承诺扫描接口）
ALLOW_CLIENT_NOW = APP_ENV in {"development", "test"}

# 写接口简易限流：窗口 60 秒内的最大写请求数
WRITE_RATE_LIMIT_PER_MINUTE = int(os.environ.get("WRITE_RATE_LIMIT_PER_MINUTE", "120"))

# CORS 允许来源
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]

# SSE keep-alive 间隔（秒）
SSE_KEEPALIVE_SECONDS = int(os.environ.get("SSE_KEEPALIVE_SECONDS", "15"))
