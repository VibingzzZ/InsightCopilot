# 知微客服副驾 —— MVP Agent 实施指南（手把手版）

> 你负责 Agent 这一层。前后端同事按同一份契约并行开发。
> 本文按「改哪个文件 → 写什么 → 为什么 → 怎么验证」组织，照着走即可。
> 每个阶段结束都必须能跑通，不要跳阶段。

---

## 0. 先明确你的边界

| 你要做 | 你不要做 |
|---|---|
| 语义理解：意图 / 情绪 / 风险事实提取 | 查数据库、写数据库 |
| 结构化产出：缺失字段、建议动作、证据 | 改业务状态（建单、退款、改承诺） |
| 确定性规则：风险分级、时间归一化、事实校验 | 真正的工单/退款/打款执行 |
| 降级：无 Key / 断网时输出 Mock 结果 | 前端渲染、HTTP 路由 |

**一句话边界**：Agent 是一个纯函数 —— 后端把业务事实查好塞进来，你返回结构化候选。

## 1. 三个已锁定的决策

1. **输入方式**：纯函数 + 后端预组装上下文。Agent 内部不查库、不发网络请求（除了模型调用）。
2. **风险分级**：统一 `L0/L1/L2/L3`，**废弃**当前的 `normal/medium/high`。理由：接口契约 `SessionListItem.risk_level` 就是 `Literal["L0","L1","L2","L3"]`，且不良反应分级也是 L0-L3，两套合并成一套。
3. **范围**：全量 MVP = 核心副驾链路 + 不良反应 L0-L3 + 事实校验 + 承诺抽取与时间归一化。
4. **L1 怎么分**：给 `RiskExtraction` 加 `severity`（`none`/`mild`/`obvious`/`severe`），由它区分 L1 与 L2，而不是靠布尔 `adverse_reaction` 硬猜。四级都有可解释的触发依据。

---

## 1.5 当前进度基线（开工前先看这个）

阶段 A 到 E 已经全部落地并通过检查。当前状态：

| 检查项 | 结果 |
|---|---|
| `python -m pytest tests/ -q` | ✅ 41 passed |
| `python -m ruff check .` | ✅ All checks passed |
| `python -m ruff format --check .` | ✅ 54 files already formatted |
| `python -m mypy app` | ✅ no issues found in 36 source files |
| `python -m app.agent.run --mock` | ✅ 三个 Case 全跑通，`degraded=True` |
| 把 `.env` 改名后重跑 pytest | ✅ 仍全绿（离线可演示） |

已完成的文件：

| 文件 | 状态 | 对应章节 |
|---|---|---|
| `app/integrations/model/gateway.py` | ✅ 惰性构造 + `is_available` + `ModelUnavailableError` | A1 |
| `app/agent/state.py` | ✅ 类型前移、去重 `order`、`degraded` 用 `or_` reducer、`RiskInfo` 含 `severity` | A2 |
| `app/agent/schemas/analysis.py` | ✅ LLM 输出 Schema（含 `severity` / `regulatory_complaint`） | B2 |
| `app/agent/schemas/contract.py` | ✅ 对外契约（前后端唯一接口源） | B1 |
| `app/agent/mock.py` | ✅ 确定性 Mock，含 `mock_severity` 三级判定 | B4 |
| `app/agent/llm.py` | ✅ `run_structured` 统一入口 + 降级 | B3 |
| `app/agent/nodes/*.py` | ✅ 10 个节点全部改造完成 | B5 |
| `app/agent/nodes/risk_engine.py` | ✅ L0-L3 规则 + `severity` | B6 |
| `app/agent/graph.py` | ✅ 证据层前移、adverse 与 reply 分离、新增 fact_check | B7 |
| `app/agent/nodes/adverse.py` | ✅ 不良反应专项（字段清单 / 工单草稿 / 处置话术） | C |
| `app/agent/time.py` + `nodes/promise.py` | ✅ 承诺抽取 + 时间归一化 | D |
| `app/agent/nodes/fact_check.py` | ✅ 事实校验（L2/L3 未核验事实阻断发送） | E |
| `app/agent/run.py` | ✅ `run_copilot` / `extract_promises` + 三个演示 Case | E2 |
| `tests/` | ✅ `test_agent.py` / `test_risk_engine.py` / `test_time.py` | E3 |

顺带修掉的坑：

- `scripts/import_excel.py` / `demo_reset.py` 原来 `from database import ...`、`from models import ...` 指向不存在的顶层模块，已改为 `app.core.database` / `app.models.models`，现在脚本能真的写库。
- `import_excel.py` 用 `db.merge()` 建 consumer/session 后直接插 `service_event`，外键约束会失败并整笔回滚（所以数据库一直是 0 行）。已在中间补 `db.flush()`。
- 删掉了与 `app/agent/schemas/contract.py` 重复的 `app/schemas/contract.py`。
- `requirements.txt` 原来被截断（末行是没写版本的 `langchain-core` 且无换行），已重写并与 `pyproject.toml` 对齐；`sqlalchemy` / `pandas` / `openpyxl` 已补进 `pyproject.toml`。

> ⚠️ 改了 `pyproject.toml` 的依赖后需要跑一次 `uv lock`，否则 CI 的 `uv sync --locked` 会失败。

**下一步**：Agent 层 MVP 目标已达成，剩余工作是接口层与联调 —— 阶段 F 的自检清单（把 `CopilotInsight` 字段名跟后端逐一核对、跟前端对齐 `needs_review` 提示）。

---

## 2. 目标架构

### 2.1 对外只有两个纯函数

```python
# app/agent/run.py
run_copilot(request: CopilotRequest) -> CopilotResult          # 对应 GET /api/sessions/{id}/copilot
extract_promises(req: PromiseExtractRequest) -> PromiseExtractResult  # 对应 POST /api/promises/extract
```

### 2.2 图结构（相对现状的关键变化）

```text
START → context → intent → emotion → risk_extraction → risk_engine
      → tool_query → evidence          ← 移到分支之前，两条路都有事实
      → conditional(risk_level)
            L1/L2/L3 → adverse ─┐
            L0 ─────────────────┴→ reply → fact_check → END
```

三个必须修的结构性问题：

1. **`tool_query`/`evidence` 挪到条件边之前**。现状 high 分支不走 evidence，reply 拿到空证据。
2. **`adverse` 不再写 `reply_draft`**。现状 `adverse → reply`，reply 又把话术覆盖了，等于高风险处置话术完全失效。改为 `adverse` 只产出 `adverse` 对象，话术由 `reply` 按 risk_level 选 prompt 生成。
3. **新增 `fact_check` 节点**在 reply 之后，校验草稿里的事实断言是否有证据支撑。

> **为什么 L1 也进 adverse**：文档给 L1 定的动作是「建议停止使用并收集信息，建立普通回访任务」，
> 这也需要不良反应的字段清单和话术，只是不建专项工单（`ticket_draft=None`）、不升级。

---

## 阶段 A：P0 修复（先做，做完再谈功能）

目标：**`python -m pytest tests/ -q` 能收集并跑通**，这是唯一验收标准。

### A1. 重写 `app/integrations/model/gateway.py`

**现状的 bug**：

```python
from openai import api_key  # ← 拿到的是 openai 模块的 api_key 属性，不是 os.getenv

...
if not model:  # ← 判断的是被 import 进来的模块对象，恒为真
    raise ValueError(...)
if not api_key:  # ← 恒为 None，所以无 Key 时 import 即崩
    raise ValueError(...)
```

后果：任何节点 `import` 时就抛异常，整个 Agent 包无法加载，**离线 Mock 演示路径被直接掐死**。实测 `pytest` 现在收集阶段就 `ERROR`。

**改成惰性 + 明确降级**：

```python
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

# 模型路由 -> (模型名环境变量, API Key 环境变量, Base URL 环境变量)
ROUTE_ENV: dict[str, tuple[str, str, str]] = {
    "fast": ("MODEL_FAST", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"),
    "reasoning": ("MODEL_DS", "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL"),
    "vision": ("MODEL_VISION", "DASHSCOPE_API_KEY", "DASHSCOPE_BASE_URL"),
}
DEFAULT_ROUTE = "fast"


class ModelUnavailableError(RuntimeError):
    """缺模型名或 API Key。调用方必须降级，不得中断链路。"""


class ModelGateway:
    def __init__(self, temperature: float = 0.5) -> None:
        self.temperature = temperature
        self._clients: dict[str, ChatOpenAI] = {}

    def _env_names(self, route: str) -> tuple[str, str, str]:
        return ROUTE_ENV.get(route, ROUTE_ENV[DEFAULT_ROUTE])

    def is_available(self, route: str = DEFAULT_ROUTE) -> bool:
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
                api_key=os.getenv(key_env, ""),
                base_url=os.getenv(base_url_env) or None,
                temperature=self.temperature,
            )
        return self._clients[route]


gateway = ModelGateway()
```

**要点**：
- 构造客户端**放在 `get()` 里**，不在 `__init__`，这样 import 永远不崩。
- 删掉 `from app.integrations import model` 这个自引用 import（原文件里有，纯属误写）。
- 补 `MODEL_VISION` 到 `.env`（可选，不存在则 vision 路由自动不可用）。

**验收**：`python -c "from app.integrations.model.gateway import gateway; print(gateway.is_available('fast'))"` —— 不报错，打印 True/False。

### A2. 修 `app/agent/state.py`

**现状两个 bug**：

```python
class CustomerState(TypedDict):
    ...
    risk: RiskInfo  # ← RiskInfo 定义在本类之后（原 :33），
    evidence: Annotated[list[EvidenceItem], add]  # noqa: F821  ← EvidenceItem 同理（原 :40）
    order: dict  # ← :27
    order: dict[str, str]  # ← :37 重复定义，后者覆盖前者
```

为什么你本地能跑：你的 `.venv` 是 Python 3.14.6（PEP 649 延迟求值）；CI 是 3.12，注解立即求值会 `NameError`。

**改法**：把 `RiskInfo` / `EvidenceRef` 定义**移到 `CustomerState` 之前**（最稳，不依赖 Python 版本），删掉两处 `# noqa: F821`，删掉重复的 `order`。字段按下面这版重写：

```python
from operator import add, or_
from typing import Annotated, TypedDict

from app.agent.schemas.contract import EvidenceRef


class RiskInfo(TypedDict):
    adverse_reaction: bool
    symptoms: list[str]
    medical_visit: bool
    regulatory_complaint: bool  # 监管投诉 / 舆情曝光 / 明确威胁


class FactCheck(TypedDict):
    status: str  # pass / needs_review
    unverified_claims: list[str]
    blocked: bool


class CustomerState(TypedDict):
    # 输入层（由 CopilotRequest 预组装）
    session_id: str
    customer_name_masked: str
    current_message: str
    messages: list[dict]
    orders: list[dict]
    tickets: list[dict]
    promises: list[dict]
    mode: str

    # 理解层
    intent: dict  # {primary, secondary, entities}
    emotion: str
    emotion_trend: str

    # 风险层
    risk: RiskInfo
    risk_level: str  # L0 / L1 / L2 / L3
    risk_reasons: list[str]

    # 数据层
    linked_order: dict
    linked_tickets: list[dict]

    # 证据层（add reducer：节点只返回新增条目）
    evidence: Annotated[list[EvidenceRef], add]

    # 处置层
    missing_fields: list[str]
    suggested_actions: list[str]
    adverse: dict | None

    # 表达层
    reply_draft: str
    fact_check: FactCheck

    # 可观测性：任一节点降级则整体降级，所以用 or_ 而不是覆盖
    degraded: Annotated[bool, or_]
    model_route: str
```

**注意**：`degraded` 用 `or_` reducer 是故意的 —— 如果多个节点都可能降级，普通覆盖会被后一个节点的 `False` 冲掉。

**验收**：`python -m mypy app` 无报错；把 `.env` 临时改名后 `python -c "import app.agent.graph"` 不报错（若阶段 B 未完成，至少 `import app.agent.state` 不报错）。

### A3. 合并冲突的回复 Schema

现状有**两个**回复 schema：

- `app/schemas/schemas.py` 的 `ReplyAnalysis{reply_draft}`（`reply.py` 在用）
- `app/agent/schemas/analysis.py` 的 `ReplyDraft{reply}`（指南要求）

**改法**：删掉 `app/schemas/schemas.py` 里的 `ReplyAnalysis`，统一用 `analysis.py` 的 `ReplyDraft`。`app/schemas/schemas.py` 保留 5 个工单 detail 白名单模型（这部分没问题，别动）。

### A4. 依赖对齐

现在两份依赖**互相矛盾，只有一份能装通**：

| 文件 | 缺什么 |
|---|---|
| `requirements.txt` | 缺 `fastapi` / `uvicorn` / `langgraph` / `langchain-openai` / `openai` / `python-dotenv` |
| `pyproject.toml` | 缺 `sqlalchemy` / `pandas` / `openpyxl` |

**改法**：以 `pyproject.toml` 为准（CI 用的就是 `uv sync --locked`），把 `sqlalchemy>=2.0`、`pandas>=2.0`、`openpyxl>=3.1` 加进 `dependencies`；`requirements.txt` 要么删掉、要么与 pyproject 保持一致。改完 `uv lock`。

### A5. 清死代码

- `nodes/risk.py`、`tests/test.py` 已在 git 中删除 → 确认无残留 import。
- **删 `tests/test2.py`**（旧手动脚本，引用了已删的 `risk_engine` 旧签名）。

**阶段 A 验收**：`python -m pytest tests/ -q` 全绿，`ruff check .`、`mypy app` 全过。

---

## 阶段 B：契约 + 核心副驾链路

### B1. 新建 `app/agent/schemas/contract.py`（前后端唯一契约源）

这是你交给后端同事的东西。字段命名**严格对齐接口设计文档**第 3、7 节。

```python
from typing import Any, Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["L0", "L1", "L2", "L3"]
ModelRoute = Literal["fast", "reasoning", "vision", "mock"]
AgentMode = Literal["auto", "real", "mock"]
SourceType = Literal["chat", "order", "ticket", "rule", "action"]


class EvidenceRef(BaseModel):
    """所有 Agent 结论的证据入口，高风险提示必须能回溯到这里。"""

    source_type: SourceType
    source_id: str
    message_id: str | None = None
    quote: str | None = None


class CopilotRequest(BaseModel):
    """后端预组装。Agent 不查库、不调外部接口。"""

    session_id: str
    current_message: str
    customer_name_masked: str | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    orders: list[dict[str, Any]] = Field(default_factory=list)
    tickets: list[dict[str, Any]] = Field(default_factory=list)
    promises: list[dict[str, Any]] = Field(default_factory=list)
    mode: AgentMode = "auto"


class CopilotInsight(BaseModel):
    intent_primary: str | None = None
    intent_secondary: str | None = None
    entities: list[str] = Field(default_factory=list)
    emotion: str = "unknown"
    emotion_trend: str = "flat"
    risk_level: RiskLevel = "L0"
    risk_reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    model_route: ModelRoute = "mock"
    degraded: bool = False


class AdverseAssessment(BaseModel):
    """只做服务风险分级：不做医学诊断，不替代医生建议。"""

    grade: Literal["L1", "L2", "L3"]
    symptom_summary: str = ""
    medical_visit: bool = False
    stopped_use: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)
    ticket_draft: dict[str, Any] | None = None  # CREATE_TICKET 的 draft_payload
    safe_reply: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    status: Literal["pass", "needs_review"] = "pass"
    unverified_claims: list[str] = Field(default_factory=list)
    blocked: bool = False


class CopilotResult(BaseModel):
    session_id: str
    insight: CopilotInsight
    draft_reply: str | None = None
    adverse: AdverseAssessment | None = None
    fact_check: FactCheckResult = Field(default_factory=FactCheckResult)


class PromiseExtractRequest(BaseModel):
    """只对客服最终发送的消息生效，草稿不进入。"""

    session_id: str
    message_id: str
    message_text: str
    mode: AgentMode = "auto"


class PromiseCandidate(BaseModel):
    promise_type: Literal["refund", "follow_up", "replenishment", "logistics", "other"] = "other"
    statement: str
    due_expression: str | None = None  # 模型识别的原始表达
    due_at: str | None = None  # 时间服务归一化结果；模糊表达为 None
    owner_type: Literal["store", "agent", "team", "system"] = "agent"
    confidence: float = 0.0
    needs_confirmation: bool = False
    evidence: list[EvidenceRef] = Field(default_factory=list)


class PromiseExtractResult(BaseModel):
    """对齐接口文档 POST /api/promises/extract 的响应结构。"""

    candidate: PromiseCandidate | None = None
    needs_confirmation: bool = False
    model_route: ModelRoute = "mock"
    degraded: bool = False
```

**给后端的两条对接约定**（写进 PR 描述里）：
- `mode=auto`（默认）：有 Key 走模型，无 Key 自动降级并置 `degraded=true`。**后端接口永远返回 200**，不要因为降级报 503。
- `mode=real`：强制走模型，缺配置会抛 `ModelUnavailableError`，仅用于开发和评测。

### B2. 扩展 `app/agent/schemas/analysis.py`

这是 **LLM 输出**的 schema，与 B1 的对外契约分开。相对现状的升级：

| Schema | 变化 | 理由 |
|---|---|---|
| `IntentAnalysis` | 单 `intent` → `intent_primary` + `intent_secondary` + `entities` | 文档要求一级/二级场景；`entities` 用于关联订单（替代现在那个没赋值的 `order_id`） |
| `EmotionAnalysis` | 加 `trend` | 文档要求「情绪变化方向」，客服要据此行动 |
| `RiskExtraction` | 加 `regulatory_complaint` + `severity` | 监管投诉是 L3 硬规则触发器；`severity` 用来区分 L1/L2，否则只有布尔值分不出轻重 |
| `ReplyDraft` | 不变（`reply`） | 唯一回复 schema |
| `PromiseExtraction` | 新增 | 承诺抽取 |

```python
class IntentAnalysis(BaseModel):
    intent_primary: str = Field(description="一级场景，如 订单服务 / 不良反应 / 物流问题 / 售前咨询")
    intent_secondary: str = Field(description="二级场景；无法判断时填 其他")
    entities: list[str] = Field(default_factory=list, description="订单号、商品名、金额、批次号、时间等实体")


class EmotionAnalysis(BaseModel):
    emotion: str = Field(description="当前主要情绪，如 平静 / 焦虑 / 不满 / 愤怒 / 急切")
    trend: str = Field(default="flat", description="情绪变化方向：up 上升 / flat 持平 / down 缓和")


class RiskExtraction(BaseModel):
    adverse_reaction: bool = Field(description="是否出现不良反应（红肿、刺痛、瘙痒、起疹、爆痘等）")
    severity: str = Field(
        default="none",
        description=(
            "不适程度，用于区分分级："
            "none 无不适 / mild 轻微泛红、刺痒或局部小颗粒且未加重 / "
            "obvious 范围扩大、持续加重、明显红肿 / severe 呼吸困难、眼部严重异常、住院"
        ),
    )
    symptoms: list[str] = Field(default_factory=list, description="症状关键词；无则空列表")
    medical_visit: bool = Field(description="是否明确表示已就医/已在医院")
    regulatory_complaint: bool = Field(description="是否提及监管投诉、平台投诉、曝光、律师或明确威胁")


class ReplyDraft(BaseModel):
    reply: str = Field(description="生成给客服编辑的回复文案")


class PromiseExtraction(BaseModel):
    has_promise: bool = Field(description="该消息中是否存在对消费者的明确承诺")
    promise_type: str = Field(default="other", description="refund / follow_up / replenishment / logistics / other")
    statement: str = Field(default="", description="标准化后的承诺内容")
    due_expression: str = Field(default="", description="时间的原始表达，如 '明天上午'、'3个工作日'；无则留空")
    owner_type: str = Field(default="agent", description="store / agent / team / system")
    confidence: float = Field(default=0.0, description="置信度 0 到 1")
```

### B3. 新建 `app/agent/llm.py`（统一调用 + 降级，**这一步是整个改造的关键**）

现在每个 LLM 节点都在**模块顶层**做这件事：

```python
gateway = ModelGateway()
parser = PydanticOutputParser(pydantic_object=XxxAnalysis)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser
```

这有三个问题：import 就会构造客户端；到处重复；**没有任何降级**。

**改法**：抽出唯一入口，返回 `(结果, 是否降级)`：

```python
import logging
from collections.abc import Callable
from typing import TypeVar

from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel

from app.integrations.model.gateway import ModelUnavailableError, gateway

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
_PARSERS: dict[type[BaseModel], PydanticOutputParser] = {}


def parser_for(schema: type[T]) -> PydanticOutputParser:
    """PydanticOutputParser 可复用，缓存避免每次重建。"""
    if schema not in _PARSERS:
        _PARSERS[schema] = PydanticOutputParser(pydantic_object=schema)
    return _PARSERS[schema]


def format_instructions(schema: type[T]) -> str:
    """节点构造 prompt 时用它拿 JSON 格式说明。"""
    return parser_for(schema).get_format_instructions()


def run_structured(
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
```

**为什么这样设计**：
- `except Exception` 是故意的 —— 文档要求「现场断网不能白屏」，宁可降级也不能让演示链路断掉。
- 降级信息通过第二个返回值向上传播，最终落到 `CopilotInsight.degraded`，前端可以显示降级角标。

### B4. 新建 `app/agent/mock.py`（确定性 Mock）

用途：① 无 Key / 断网演示；② 单测不依赖外部模型。**全部关键词规则，不引入随机**。

每个 LLM schema 配一个 mock 函数，签名与真实调用一致：

```python
def mock_intent(message: str) -> IntentAnalysis
def mock_emotion(message: str) -> EmotionAnalysis
def mock_risk(message: str) -> RiskExtraction
def mock_reply(risk_level: str, evidence_lines: list[str]) -> ReplyDraft
def mock_promise(message_text: str) -> PromiseExtraction
```

关键词表（建议按这个来）：

| 类别 | 词表 |
|---|---|
| 症状 | 红肿、泛红、脸红、刺痛、疼痛、很疼、疼、瘙痒、发痒、痒、起疹、疹子、爆痘、痘痘、肿胀、过敏、脱皮、灼热 |
| 就医 | 医院、就医、医生、挂号、住院、急诊、门诊、挂了号 |
| 监管投诉 | 12315、消协、监管、曝光、起诉、律师、媒体、工商 |
| 焦虑 | 着急、急、还没、怎么还、等很久、催、多久 |
| 愤怒 | 太差、差劲、骗子、无语、垃圾、投诉 |
| 退款 | 退款、打款、到账、价保、退钱 |
| 物流 | 快递、物流、发货、到货、签收、包裹、运单 |

⚠️ 注意：**普通「投诉」不进监管投诉词表**（只进愤怒）。否则大量普通抱怨会被误判成 L3，导致告警疲劳 —— 文档专门列了这个风险。

`mock_risk` 还要按顺序判出 `severity`（顺序不能反，严重的先判）：

```python
SEVERE_WORDS = ("呼吸困难", "喘不上气", "眼部", "眼睛肿", "住院", "晕倒")  # → severe
OBVIOUS_WORDS = ("加重", "扩大", "越来越", "一直没好", "整个脸", "大面积")  # → obvious
MILD_ONLY = ("有点", "轻微", "一点点", "小颗粒", "局部")  # → mild
```

判定顺序：命中 `MEDICAL_WORDS` 或 `SEVERE_WORDS` → `severe`；命中 `OBVIOUS_WORDS` → `obvious`；
命中症状词（`SYMPTOM_WORDS`）→ `mild`；否则 `none`。
> 医疗词优先，是因为「已就医」本身在文档里就是 L3 的判定依据，程度一定不轻。


`mock_reply` 按 risk_level 出三套模板：L3 出「停止使用 + 建议就医 + 已升级专员」；L1/L2 出「暂停使用 + 收集部位和时间」；L0 出「已核实事实 + 询问还需什么」。**任何一套都不允许出现病名、病因、用药建议。**

### B5. 逐个改造节点

统一模式（以 intent 为例）：

```python
from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_intent
from app.agent.schemas.analysis import IntentAnalysis
from app.agent.state import CustomerState
from app.prompt.intent_prompt import INTENT_PROMPT


def intent_node(state: CustomerState) -> dict:
    prompt = INTENT_PROMPT.format(
        message=state["current_message"],
        format_instructions=format_instructions(IntentAnalysis),
    )
    result, degraded = run_structured(
        prompt=prompt,
        schema=IntentAnalysis,
        route="fast",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_intent(state["current_message"]),
    )
    return {
        "intent": {
            "primary": result.intent_primary,
            "secondary": result.intent_secondary,
            "entities": result.entities,
        },
        "degraded": degraded,
    }
```

**注意**：所有节点改成 `-> dict` 且**只返回改动字段**。现状 `intent.py` / `emotion.py` 的签名写的是 `-> CustomerState`（虽然实际返回 dict），`adverse.py` 也是，顺手统一掉。

逐个节点的差异：

| 节点 | 路由 | 改动要点 |
|---|---|---|
| `context` | — | 从 `CopilotRequest` 拷输入字段；决定 `mode` 与 `model_route`；`model_route = "mock" if 不可用 else "reasoning"` |
| `intent` | `fast` | 见上 |
| `emotion` | `fast` | 额外返回 `emotion_trend` |
| `risk_extraction` | `reasoning` | 只提事实，**不下等级**。这是「模型提事实、代码定规则」的分工 |
| `risk_engine` | 纯代码 | 见 B6 |
| `tool_query` | 纯代码 | **不再查 mock 字典**。改为从 `state["orders"]` 里按 `intent.entities` 匹配出 `linked_order`；从 `state["tickets"]` 里按订单/会话关联出 `linked_tickets`。匹配不到就返回空 dict，不编造 |
| `evidence` | 纯代码 | 把 `linked_order` / `linked_tickets` 压成 `EvidenceRef[]`，返回新增条目（`add` reducer 自动累加） |
| `adverse` | 纯代码 | 见阶段 C |
| `reply` | `reasoning` | 按 `risk_level` 选两套 prompt（普通 / 高风险处置）。**L3 时必须以 `adverse.safe_reply` 为骨架**，避免模型自由发挥 |
| `fact_check` | 纯代码 | 见阶段 E |

### B6. `risk_engine.py` 改成 L0-L3

```python
from app.agent.state import CustomerState

SEVERE_SYMPTOMS = ("呼吸困难", "喘不上气", "眼部", "眼睛肿", "住院", "晕倒")


def risk_engine_node(state: CustomerState) -> dict:
    risk = state["risk"]
    severity = risk.get("severity", "none")
    emotion = state["emotion"]
    strong_emotion = emotion in {"愤怒", "急切", "不满"}
    reasons: list[str] = []

    # L3：已就医 / 监管投诉 / 严重程度，任一命中直接最高级（文档 §6.3）
    if risk["medical_visit"]:
        reasons.append("消费者已就医")
    if risk["regulatory_complaint"]:
        reasons.append("提及监管投诉或舆情曝光")
    if severity == "severe" or any(s in risk["symptoms"] for s in SEVERE_SYMPTOMS):
        reasons.append("症状较严重")

    if reasons:
        return {"risk_level": "L3", "risk_reasons": reasons}

    # L2：范围扩大/持续加重/明显红肿，或出现不良反应且情绪强烈
    if severity == "obvious":
        reasons.append("症状明显（范围扩大或持续加重）")
    elif risk["adverse_reaction"] and strong_emotion:
        reasons.append("出现不良反应且情绪强烈")

    if reasons:
        return {"risk_level": "L2", "risk_reasons": reasons}

    # L1：轻微不适且未加重
    if risk["adverse_reaction"] or severity == "mild":
        return {"risk_level": "L1", "risk_reasons": ["出现轻微不良反应，尚未加重"]}

    # L0：普通咨询
    return {"risk_level": "L0", "risk_reasons": []}
```

**注意两点**：

- `severity` 用 `risk.get(...)` 而不是 `risk[...]`：Mock 或旧数据可能没这个 key，不能让规则节点崩。
- **单纯情绪不满不升级**（只记入 `emotion` / `emotion_trend`）。文档风险表明确列了「风险提示过多 → 客服告警疲劳」，情绪单因素不该独立触发 L2。

**四级汇总**（便于你写 `tests/test_risk_engine.py` 的边界用例）：

| 等级 | 触发条件 | 系统动作 |
|---|---|---|
| L3 | 已就医 / 监管投诉 / `severity=severe` | 升级专员与主管、建高优工单、限制自由回复、持续跟踪 |
| L2 | `severity=obvious`，或出现不良反应且情绪强烈 | 提示及时就医、建高优工单、升级专员 |
| L1 | 出现轻微不良反应且未加重 | 建议停止使用、收集信息、建普通回访任务（**不建专项工单**） |
| L0 | 其余（含单纯情绪抱怨） | 正常接待 |

> 文档要求「L2 和 L3 不得由系统自动降级」—— 所以这个节点的输出只作为**初始等级**，
> 后续人工调级走后端 `PATCH` 接口并记录理由，Agent 不做「自动降级」。

### B7. `graph.py` 接线

```python
def route_by_risk(state: CustomerState) -> str:
    return "adverse" if state["risk_level"] in {"L1", "L2", "L3"} else "normal"


builder.add_edge(START, "context")
builder.add_edge("context", "intent")
builder.add_edge("intent", "emotion")
builder.add_edge("emotion", "risk_extraction")
builder.add_edge("risk_extraction", "risk_engine")
builder.add_edge("risk_engine", "tool_query")  # 两条路都先查事实
builder.add_edge("tool_query", "evidence")
builder.add_conditional_edges(
    "evidence",
    route_by_risk,
    {"adverse": "adverse", "normal": "reply"},
)
builder.add_edge("adverse", "reply")
builder.add_edge("reply", "fact_check")
builder.add_edge("fact_check", END)
```

**阶段 B 验收**：`python -m app.agent.run --mock` 三个 Case 都能打印出 intent / emotion / risk_level / evidence / reply，且 `degraded=True`。

---

## 阶段 C：不良反应 L0-L3 专项

**重写 `app/agent/nodes/adverse.py`，纯代码，不调模型。**

职责四条：

1. **产出 `AdverseAssessment`**（`grade` / `symptom_summary` / `medical_visit` / `stopped_use`）。
2. **信息收集清单**：对照 `AdverseReactionDetail`（`app/schemas/schemas.py` 已有白名单）逐项检查已有事实，**只把缺的列进 `missing_fields`**。顺序建议：批次号 → 使用部位 → 出现时间 → 是否停用 → 是否就医 → 图片资料。已经是消费者说过的字段绝不能再问（文档明确要求「避免重复询问」）。
3. **`ticket_draft`**：生成 `CREATE_TICKET` 的 `draft_payload`，`priority` 按等级给（L3→`critical`，L2→`urgent`）。**只产出草稿，不建单** —— 建单是后端 `POST /api/actions/confirm` 的事。**L1 时 `ticket_draft = None`**，只建普通回访任务。
4. **`safe_reply`**：规则化处置话术，**不含病名、病因、用药建议**。三档分开写：
   - **L1**：暂停使用 + 请告知使用部位和出现时间 + 我们会持续跟进。
   - **L2**：暂停使用 + 建议及时寻求专业医疗帮助 + 已升级专员。
   - **L3**：必须以「请立即就医、以医生意见为准」开头 + 已升级主管和专项团队 + 会持续跟踪。

```python
def adverse_node(state: CustomerState) -> dict:
    if state["risk_level"] not in {"L1", "L2", "L3"}:
        return {}

    grade = state["risk_level"]
    risk = state["risk"]
    order = state["linked_order"]

    # 已确认字段自动回填，只把缺的列进 missing_fields（绝不重复询问消费者已说过的）
    missing = [f for f, present in _FIELD_PRESENCE.items() if not present(state)]
    ticket_draft = None if grade == "L1" else _build_ticket_draft(state, grade)
    actions = _build_actions(grade)

    assessment = AdverseAssessment(
        grade=grade,
        symptom_summary="、".join(risk["symptoms"]) or "消费者自述不适",
        medical_visit=risk["medical_visit"],
        stopped_use=None,
        missing_fields=missing,
        ticket_draft=ticket_draft,
        safe_reply=_safe_reply(grade, "、".join(risk["symptoms"]), order.get("product_name") or "该产品"),
        suggested_actions=actions,
    )
    return {
        "adverse": assessment.model_dump(),
        "missing_fields": missing,
        "suggested_actions": actions,
    }
```

- `_FIELD_PRESENCE`：字段 → 判断函数 的映射（批次号看 `order`，使用部位/出现时间/是否停用看 `messages` 里是否已被问过或答过）。这是「避免重复询问」的实现点，值得写成一张显式表。
- `suggested_actions` 按等级给：L1 只给「登记普通回访」；L2 加「创建不良反应工单 + 升级专员」；L3 再加「升级主管 + 24 小时内回访」。

**验收**：
- 「用了面霜脸特别红、很疼、已经去医院了」→ `grade == "L3"`，`missing_fields` 里**不能**出现「是否就医」。
- 「用了之后有点轻微泛红」→ `grade == "L1"`，`ticket_draft is None`，`suggested_actions` 里有普通回访。
- 「脸整个肿了，越来越严重」→ `grade == "L2"`（`severity=obvious`）。

---

## 阶段 D：承诺抽取 + 时间归一化

这是第二块标志性能力，也是答辩最容易拿分的部分。**关键是模型和确定性代码的分工**：模型只负责读懂「明天上午」这个表达，实际截止时间由代码算。

### D1. 新建 `app/agent/time.py`（纯函数，无依赖）

```python
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
VAGUE_WORDS = ("尽快", "稍后", "晚点", "抽空", "第一时间", "有空", "回头")
END_OF_BUSINESS_HOUR = 18
_CN_NUM = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def normalize_due(
    expression: str | None,
    now: datetime | None = None,
    holidays: set[str] | None = None,
) -> tuple[str | None, bool]:
    """把自然语言时间表达归一化为 ISO8601 截止时间。

    返回 (due_at, needs_confirmation)：
      - 无法确定（尽快/稍后/空）→ (None, True)，由人工补明确时间，绝不编造截止时间
      - 可确定 → (ISO8601 字符串, False)
    """
```

要覆盖的规则（文档 §7.3 逐条要求）：

| 表达 | 结果 |
|---|---|
| `N小时` / `N小时内` | now + N 小时 |
| `N个工作日` | 往后数 N 个工作日（跳过周末 + `holidays`），取当日 18:00 |
| `N天` / `N个自然日` | now + N 天，取当日 18:00 |
| `今天18:00前` / `今天下午3点` | 当日该时刻 |
| `今天下班前` | 当日 18:00 |
| `明天上午` | 次日 12:00 |
| `明天下午` / `明天` | 次日 18:00 |
| `尽快` / `稍后` / 空 | `(None, True)` |

**必须区分**：「3 个工作日」和「72 小时」结果不同（周末会岔开）—— 这是文档点名要验的点。
**假期表**：先用可传入的 `holidays: set[str]`（`YYYY-MM-DD`），默认空集，后续接配置表。不要硬编码节假日。

### D2. 新建 `app/agent/nodes/promise.py`

```python
def extract_promise_candidate(req: PromiseExtractRequest) -> PromiseExtractResult:
    prompt = PROMISE_EXTRACT_PROMPT.format(
        message=req.message_text, format_instructions=format_instructions(PromiseExtraction)
    )
    result, degraded = run_structured(
        prompt=prompt, schema=PromiseExtraction, route="fast",
        mode=req.mode, fallback=lambda: mock_promise(req.message_text),
    )
    if not result.has_promise:
        return PromiseExtractResult(candidate=None, model_route=..., degraded=degraded)

    due_at, needs_confirmation = normalize_due(result.due_expression)
    candidate = PromiseCandidate(
        promise_type=result.promise_type if result.promise_type in PROMISE_TYPES else "other",
        statement=result.statement or req.message_text,
        due_expression=result.due_expression or None,
        due_at=due_at,
        owner_type=result.owner_type,
        confidence=result.confidence,
        needs_confirmation=needs_confirmation,
        evidence=[EvidenceRef(source_type="chat", source_id=req.message_id, message_id=req.message_id, quote=req.message_text[:50])],
    )
    return PromiseExtractResult(candidate=candidate, needs_confirmation=needs_confirmation, ...)
```

**注意**：`promise_type` 是模型自由输出的字符串，**必须校验落在白名单里**，否则会污染数据库的 `promise_type` 字段。

**验收**（文档点名）：
```python
normalize_due("明天上午")  # (明天12:00, False)
normalize_due("3 个工作日")  # (跳过周末后的18:00, False)
normalize_due("72小时")  # (now+72h, False) —— 与上面结果必须不同
normalize_due("尽快")  # (None, True)
```

---

## 阶段 E：事实校验 + 测试

### E1. 新建 `app/agent/nodes/fact_check.py`（纯代码）

作用：**成本最低、最能体现「不虚构」的一环**。文档要求「金额、状态、时间与业务数据不一致时阻断发送」。

```python
def fact_check_node(state: CustomerState) -> dict:
    draft = state["reply_draft"]
    evidence_text = " ".join(f"{e.content or ''}" for e in state["evidence"])
    claims = _extract_claims(draft)  # 抽金额 / 时间 / 状态词
    unverified = [c for c in claims if c not in evidence_text]
    ...
```

抽什么：
- 金额：`\d+(\.\d+)?\s*元`、`\d+\s*块`
- 时间：`\d{1,2}\s*月\s*\d{1,2}\s*日`、`\d+\s*个?\s*工作日`、`\d+\s*小时`、`\d{1,2}\s*[:点]\s*\d{0,2}`
- 状态词：`已发货`、`已退款`、`已签收`、`处理中`、`已到账`

命中证据 → 通过；未命中 → 进 `unverified_claims`，`status = needs_review`。
**阻断规则**：L2/L3 场景 + 未核验的金额/状态 → `blocked = True`（高风险不允许带未核实证事实发送）。普通场景只标记不阻断。

⚠️ 不做第二次 LLM 审查 —— 文档性能目标明确要求「普通会话不运行视觉模型和第二次大模型审查」。

### E2. `app/agent/run.py` 改成正式入口

```python
def run_copilot(request: CopilotRequest) -> CopilotResult:
    state = _make_state(request)
    final = graph.invoke(state)
    return CopilotResult(
        session_id=request.session_id,
        insight=CopilotInsight(
            intent_primary=final["intent"].get("primary"),
            intent_secondary=final["intent"].get("secondary"),
            entities=final["intent"].get("entities", []),
            emotion=final["emotion"],
            emotion_trend=final["emotion_trend"],
            risk_level=final["risk_level"],
            risk_reasons=final["risk_reasons"],
            missing_fields=final["missing_fields"],
            suggested_actions=final["suggested_actions"],
            evidence=final["evidence"],
            model_route=final["model_route"],
            degraded=final["degraded"],
        ),
        draft_reply=final["reply_draft"] or None,
        adverse=AdverseAssessment(**final["adverse"]) if final["adverse"] else None,
        fact_check=FactCheckResult(**final["fact_check"]),
    )


def extract_promises(req: PromiseExtractRequest) -> PromiseExtractResult: ...
```

CLI：`python -m app.agent.run --mock` / `--case 不良反应` / 不带参数跑真实模型。

⚠️ `_make_state` **必须把所有 key 都初始化**（TypedDict 缺 key 会 KeyError）。三个 Case 的样例上下文（订单/工单/历史消息）建议直接写死在 `run.py` 的 `CASES` 里，这样离线可复现，也方便后端对照你要什么字段。

### E3. 测试重写

| 文件 | 内容 |
|---|---|
| `tests/test_agent.py` | 重写。三个 Case 走 `mode="mock"` 端到端：断言 `risk_level`、`evidence` 非空、`draft_reply` 非空、不良反应 Case 的 `adverse` 非空且 `grade == "L3"` |
| `tests/test_risk_engine.py` | 新建。L0-L3 四档边界：已就医→L3、监管投诉→L3、`severity=severe`→L3、`severity=obvious`→L2、不良反应+愤怒→L2、轻微泛红→**L1**、仅情绪不满→L0 |
| `tests/test_time.py` | 新建。见 D1 验收表，**必须包含「3 个工作日 ≠ 72 小时」这条** |
| `tests/test_health.py` | 不用动 |

**为什么必须用 `mode="mock"` 写单测**：CI 没有 API Key（这是对的，Key 不该进仓库）。测真实模型会挂，且每次结果不稳定。

---

## 阶段 F：与后端/前端联调前必须自检

- [ ] `python -m app.agent.run --mock` 无 Key 全绿，`degraded=True`
- [ ] 临时把 `.env` 改名，`pytest` 仍全绿（证明离线可演示）
- [ ] `CopilotInsight` 字段名与接口文档 `CopilotInsight` 逐一核对（后端要按这份渲染）
- [ ] 任意高风险输出都能在 `evidence` 里找到对应 `source_id`
- [ ] 不良反应输出里搜不到病名、病因、用药建议
- [ ] `promise` 的 `due_at` 全部来自 `time.py`，模型只提供 `due_expression`
- [ ] `fact_check.status == "needs_review"` 时前端有明确提示（这条要跟前端同事对齐）

---

## 附：几个容易踩的坑

1. **`response_format={"type": "json_object"}` 的 prompt 里必须出现 "json" 字样**，否则 deepseek 直接报错。改 prompt 时别把这句删了。
2. **节点只能返回 `{"字段": 新值}`**，不要 `state["x"] = ...` 后 `return state`（现在的 `intent.py` / `emotion.py` / `adverse.py` 就是这个反模式，功能上没坏但和约定不一致，且容易被后续改动带偏）。
3. **`evidence` 依赖 `add` reducer**：节点返回 `{"evidence": [新条目]}`，**不要**就地 `append`。
4. **`degraded` 用 `or_` reducer**：不要用普通覆盖，否则多节点降级会被冲掉。
5. **改了 state 字段一定要同步 `_make_state`**，否则缺 key 报错。
6. **`route_by_risk` 返回的字符串必须与 `add_conditional_edges` 映射的 key 完全一致**，否则图直接 `ValueError`。
7. 模型路由：`fast` 用于意图/情绪/承诺（短任务），`reasoning` 用于风险提取/回复草稿。这是文档的成本优化要求，别所有节点都上大模型。
