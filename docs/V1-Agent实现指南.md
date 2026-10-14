# V1 Copilot Agent 实现指南

> 目标：把当前「LangGraph 骨架 + 几个 LLM 节点」升级成一条真正的链：
> **LLM 理解 → 结构化事实 → 代码决策 → 工具执行 → 证据汇总 → LLM 表达**

按五个阶段推进，每阶段结束都能跑通、能验证。最后用三个 Case 验收。

---

## 阶段 0：补依赖（必须先做）

`pyproject.toml` 的 `dependencies` 里没有 LangGraph 相关包，但代码已经 import 了。先补上：

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "pydantic>=2.7",
    "langgraph>=1.0",
    "langchain-core>=1.0",
    "langchain-openai>=1.0",
    "python-dotenv>=1.0",
]
```

`.venv` 里实际装的是 langgraph 1.2.11 / langchain-core 1.6.3 / langchain-openai 1.6.2 / python-dotenv 1.2.3，版本约束写成 `>=` 即可。改完同步一下锁文件（`uv sync` 或 `uv lock`）。

---

## 先搞懂：LangGraph 三个核心概念

第一次写 LangGraph，只记这三点就够了：

**1. Node（节点）= 一个普通函数**
- 入参：`state`（一个 dict，所有节点共享）
- 返回值：`dict`（**只返回你改动的字段**，LangGraph 会自动合并回 state）

```python
def intent_node(state: CustomerState) -> dict:
    return {"intent": "退款进度咨询"}  # 只返回改动，不返回整个 state
```

**2. Edge（边）= 连线**
- `add_edge("a", "b")`：a 跑完 → b
- `add_conditional_edges("a", 路由函数, {"分支名": "目标节点"})`：按 state 分流

**3. State = TypedDict**
- 定义所有节点共享的字段。每个字段都要在初始 state 里给个值。

> ⚠️ 最容易踩的坑：**不要**在节点里 `state["xxx"].append(...)` 靠原地修改。正确做法是返回 `{"xxx": 新值}`。

---

## 目标 State 设计（贯穿全五阶段）

```python
# app/agent/state.py
from operator import add
from typing import Annotated, TypedDict


class RiskInfo(TypedDict):
    """Risk Extraction 的结构化输出，由 LLM 提取。"""

    adverse_reaction: bool
    symptoms: list[str]
    medical_visit: bool


class EvidenceItem(TypedDict):
    """统一证据结构：Reply 只信这一层，不信原始数据。"""

    source: str  # order / ticket / logistics / ...
    id: str
    content: str


class CustomerState(TypedDict):
    # 输入
    conversation_id: str
    current_message: str

    # 理解层
    intent: str
    emotion: str

    # 风险层
    risk: RiskInfo  # Risk Extraction 产出（LLM）
    risk_level: str  # Risk Engine 判定（代码）：normal / medium / high

    # 数据层
    order: dict[str, str]  # 工具查询结果

    # 证据层（用 add reducer 累加：节点返回新增条目，LangGraph 自动 append）
    evidence: Annotated[list[EvidenceItem], add]

    # 表达层
    reply_draft: str
```

**为什么 `evidence` 要用 `Annotated[list, add]`？**
- LangGraph 默认对 `list` 字段是「覆盖」，不是「累加」。
- 加了 `add` reducer 后，节点返回 `{"evidence": [新条目]}`，框架会自动拼到已有列表后面。
- 这样证据节点才是真正的「汇总」，以后 ticket / logistics 都往里加也不打架。

---

## 阶段 1：Risk 拆分（Risk Extraction + Risk Engine）

### 要动/建的文件

| 操作 | 文件 |
|---|---|
| 新建 | `app/agent/nodes/risk_extraction.py` |
| 新建 | `app/agent/nodes/risk_engine.py` |
| 新建 | `app/prompt/risk.py` |
| 修改 | `app/agent/schemas/analysis.py`（加 `RiskExtraction`） |
| 修改 | `app/agent/state.py`（加 `risk` / `risk_level` 字段） |
| 删除 | `app/agent/nodes/risk.py`（旧的硬编码节点） |

### 1.1 加 Pydantic 结构（LLM 输出用）

```python
# app/agent/schemas/analysis.py（在现有基础上追加）
class RiskExtraction(BaseModel):
    adverse_reaction: bool = Field(description="用户是否出现不良反应（红肿、疼痛、起疹等）")
    symptoms: list[str] = Field(description="症状关键词列表，如 ['脸红','疼痛']；无则空列表")
    medical_visit: bool = Field(description="用户是否明确表示已就医/去医院")
```

### 1.2 风险提取 prompt

```python
# app/prompt/risk.py
RISK_EXTRACTION_PROMPT = """你是美妆电商客服风险识别助手。请从用户消息中提取风险信息。

用户消息：
{message}

要求：
1. adverse_reaction 判断是否出现不良反应（脸红、肿、疼、起疹等）
2. symptoms 提取症状关键词
3. medical_visit 判断用户是否表示已经就医

请严格按照 JSON 格式输出（不要输出 JSON 以外的任何内容）：
{format_instructions}"""
```

### 1.3 Risk Extraction 节点（LLM）

```python
# app/agent/nodes/risk_extraction.py
from langchain_core.output_parsers import PydanticOutputParser

from app.agent.schemas.analysis import RiskExtraction
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelGateway
from app.prompt.risk import RISK_EXTRACTION_PROMPT

gateway = ModelGateway()

# 和 intent/emotion 完全一致的模式：
# deepseek-flash 只支持 response_format={"type": "json_object"}，prompt 里必须有 "json" 字样
parser = PydanticOutputParser(pydantic_object=RiskExtraction)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser


def risk_extraction_node(state: CustomerState) -> dict:
    prompt = RISK_EXTRACTION_PROMPT.format(
        message=state["current_message"],
        format_instructions=parser.get_format_instructions(),
    )

    result: RiskExtraction = structured_llm.invoke(prompt)

    # Pydantic 对象 → dict，塞进 state["risk"]
    return {"risk": result.model_dump()}
```

### 1.4 Risk Engine 节点（纯代码规则）

```python
# app/agent/nodes/risk_engine.py
from app.agent.state import CustomerState


def risk_engine_node(state: CustomerState) -> dict:
    risk = state["risk"]

    # 业务规则：这里有不良反应 + 已就医 → 高风险
    if risk["adverse_reaction"] and risk["medical_visit"]:
        risk_level = "high"
    elif risk["adverse_reaction"]:
        risk_level = "medium"
    else:
        risk_level = "normal"

    return {"risk_level": risk_level}
```

**这个节点的意义**：风险等级不是 LLM「拍脑袋」给的，而是 LLM 提取**结构化事实**后，由**代码规则**决定等级。这样规则可测试、可解释、可改，不依赖模型当天的心情。

### 1.5 本阶段验证

单独跑一下风险两个节点（临时脚本或 `python -c`）：

```python
# 期望：adverse_reaction=True, medical_visit=True, risk_level="high"
state = {
    "conversation_id": "S",
    "current_message": "用了面霜之后脸红，而且去了医院",
    "intent": "",
    "emotion": "",
    "risk": {},
    "risk_level": "",
    "order": {},
    "evidence": [],
    "reply_draft": "",
}
state.update(risk_extraction_node(state))
print(state["risk"])  # {'adverse_reaction': True, 'symptoms': ['脸红'], 'medical_visit': True}
state.update(risk_engine_node(state))
print(state["risk_level"])  # high
```

---

## 阶段 2：修 Graph

目标图：

```text
START → Context → Intent → Emotion → Risk Extraction → Risk Engine
                                                        │
                                          Conditional Edge
                                            ├─ normal → Tool Query → Evidence ─┐
                                            └─ high   → Adverse ───────────────┴→ Reply → END
```

关键变化：
1. `risk` 一个节点 → `risk_extraction` + `risk_engine` 两个节点
2. `normal` 分支进 `tool_query`（原来直接进 evidence）
3. **`adverse` 改接到 `reply`**（原来错误地接 `END`）

```python
# app/agent/graph.py
from langgraph.graph import END, START, StateGraph

from app.agent.nodes.adverse import adverse_node
from app.agent.nodes.context import context_node
from app.agent.nodes.emotion import emotion_node
from app.agent.nodes.evidence import evidence_node
from app.agent.nodes.intent import intent_node
from app.agent.nodes.reply import reply_node
from app.agent.nodes.risk_engine import risk_engine_node
from app.agent.nodes.risk_extraction import risk_extraction_node
from app.agent.nodes.tool_query import tool_query_node
from app.agent.state import CustomerState


def route_by_risk(state: CustomerState) -> str:
    if state["risk_level"] == "high":
        return "high"
    return "normal"


builder = StateGraph(CustomerState)

builder.add_node("context", context_node)
builder.add_node("intent", intent_node)
builder.add_node("emotion", emotion_node)
builder.add_node("risk_extraction", risk_extraction_node)
builder.add_node("risk_engine", risk_engine_node)
builder.add_node("tool_query", tool_query_node)
builder.add_node("evidence", evidence_node)
builder.add_node("adverse", adverse_node)
builder.add_node("reply", reply_node)

builder.add_edge(START, "context")
builder.add_edge("context", "intent")
builder.add_edge("intent", "emotion")
builder.add_edge("emotion", "risk_extraction")
builder.add_edge("risk_extraction", "risk_engine")
builder.add_conditional_edges(
    "risk_engine",
    route_by_risk,
    {"normal": "tool_query", "high": "adverse"},
)
builder.add_edge("tool_query", "evidence")
builder.add_edge("evidence", "reply")
builder.add_edge("adverse", "reply")  # ← 关键：high 分支也汇入 reply
builder.add_edge("reply", END)

graph = builder.compile()
```

> 注意：`route_by_risk` 返回的字符串必须和 `add_conditional_edges` 里映射的 key 完全一致（这里都是 `"normal"` / `"high"`）。

---

## 阶段 3：Tool（Context 不再查订单）

### 要动/建的文件

| 操作 | 文件 |
|---|---|
| 修改 | `app/agent/nodes/context.py`（移除 `query_order`） |
| 新建 | `app/agent/nodes/tool_query.py` |
| 修改 | `app/agent/tools/order.py`（mock 数据补全） |
| 暂不做 | `tools/customer.py` / `ticket.py` / `knowledge.py`（V1 之后） |

### 3.1 Context 变成「只加载上下文」

```python
# app/agent/nodes/context.py
from app.agent.state import CustomerState


def context_node(state: CustomerState) -> dict:
    # 加载会话上下文。
    # V1：先用 conversation_id 占位，不查任何业务数据。
    # 后续：从数据库按 conversation_id 拉取历史消息。
    return {}
```

### 3.2 Tool Query 节点（查询业务数据）

```python
# app/agent/nodes/tool_query.py
from app.agent.state import CustomerState
from app.agent.tools.order import query_order


def tool_query_node(state: CustomerState) -> dict:
    # 根据 intent 路由到具体工具；V1 只接了订单工具。
    # 未来：物流 → query_logistics，工单 → query_ticket。
    intent = state["intent"]

    if intent in {"退款进度咨询", "物流进度", "订单查询"}:
        order = query_order("0001")  # TODO: 换成从会话/数据库关联真实订单号
        return {"order": order}

    return {"order": {}}
```

### 3.3 订单工具（V1 唯一要做的 tool）

```python
# app/agent/tools/order.py
MOCK_ORDERS = {
    "0001": {
        "order_id": "0001",
        "status": "退款处理中",
        "product": "某护肤产品",
        "logistics": "暂无物流信息",
    },
    "0002": {
        "order_id": "0002",
        "status": "已发货",
        "product": "某面霜",
        "logistics": "运输中，预计 2 天后送达",
    },
}


def query_order(order_id: str) -> dict:
    """查询订单。V1 用 mock 数据，后续接真实数据库/接口。"""
    return MOCK_ORDERS.get(order_id, {})
```

> 工具函数的签名保持「输入参数 → 返回 dict」，这样以后接真 DB 或 API 时只改内部实现，不改调用方。

---

## 阶段 4：Evidence 统一结构

### 要动的文件

| 操作 | 文件 |
|---|---|
| 修改 | `app/agent/nodes/evidence.py`（统一结构 + 返回新条目） |
| 已改 | `app/agent/state.py`（`EvidenceItem` + `add` reducer，阶段 0 已做） |

```python
# app/agent/nodes/evidence.py
from app.agent.state import CustomerState


def evidence_node(state: CustomerState) -> dict:
    order = state["order"]
    items = []

    if order:
        items.append(
            {
                "source": "order",
                "id": order["order_id"],
                "content": f"订单状态：{order['status']}",
            }
        )

    # 未来追加：
    # items.append({"source": "ticket", "id": "T001", "content": "客服工单处理中"})
    # items.append({"source": "logistics", "id": order["order_id"], "content": order["logistics"]})

    # 因为 evidence 字段用了 add reducer，这里返回新增条目即可，框架自动累加
    return {"evidence": items}
```

**为什么这是关键一步**：Reply 节点只读 `state["evidence"]`，不看 `state["order"]` 原始字段。这样以后证据来源变成 ticket、logistics 时，Reply 不用改，因为所有来源都被压成同一种结构 `{source, id, content}`。

---

## 阶段 5：Reply（LLM 生成 + 补 prompt）

### 要动/建的文件

| 操作 | 文件 |
|---|---|
| 新建 | `app/prompt/reply.py` |
| 修改 | `app/agent/schemas/analysis.py`（加 `ReplyDraft`） |
| 修改 | `app/agent/nodes/reply.py`（LLM 生成） |

### 5.1 Reply 结构

```python
# app/agent/schemas/analysis.py（追加）
class ReplyDraft(BaseModel):
    reply: str = Field(description="生成给用户的回复文案")
```

### 5.2 Reply prompt

```python
# app/prompt/reply.py
REPLY_PROMPT = """你是美妆电商客服助手。根据以下信息生成对用户的回复。

用户意图：{intent}
用户情绪：{emotion}
事实证据：{evidence}

要求：
1. 回复必须基于"事实证据"，不得编造不存在的订单/物流信息
2. 语气与用户情绪匹配（用户生气/着急时先安抚）
3. 简洁自然，像真人客服，不要机械模板

请严格按照 JSON 格式输出（不要输出 JSON 以外的任何内容）：
{format_instructions}"""
```

### 5.3 Reply 节点（LLM）

```python
# app/agent/nodes/reply.py
from langchain_core.output_parsers import PydanticOutputParser

from app.agent.schemas.analysis import ReplyDraft
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelGateway
from app.prompt.reply import REPLY_PROMPT

gateway = ModelGateway()

parser = PydanticOutputParser(pydantic_object=ReplyDraft)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser


def reply_node(state: CustomerState) -> dict:
    prompt = REPLY_PROMPT.format(
        intent=state["intent"],
        emotion=state["emotion"],
        evidence=state["evidence"],
        format_instructions=parser.get_format_instructions(),
    )

    result: ReplyDraft = structured_llm.invoke(prompt)

    return {"reply_draft": result.reply}
```

> ⚠️ 补充：`app/agent/schemas/analysis.py` 里现有 `EmotionAnalysis` 的 description 写成了「护腰情绪」，应该是「情绪」的错别字，顺手改掉。

---

## 验收：三个 Case

重写 `app/agent/run.py`：

```python
# app/agent/run.py
from app.agent.graph import graph
from app.agent.state import CustomerState


def make_state(message: str) -> CustomerState:
    return {
        "conversation_id": "S00005",
        "current_message": message,
        "intent": "",
        "emotion": "",
        "risk": {"adverse_reaction": False, "symptoms": [], "medical_visit": False},
        "risk_level": "",
        "order": {},
        "evidence": [],
        "reply_draft": "",
    }


CASES = {
    "退款": "我上次已经问过了，为什么还没退款？",
    "不良反应": "用了这个面霜以后脸特别红，而且很疼，我已经去医院了。",
    "物流": "我的快递怎么还没到？",
}


if __name__ == "__main__":
    for name, message in CASES.items():
        print(f"\n===== Case: {name} =====")
        result = graph.invoke(make_state(message))
        print("intent     :", result["intent"])
        print("emotion    :", result["emotion"])
        print("risk       :", result["risk"])
        print("risk_level :", result["risk_level"])
        print("evidence   :", result["evidence"])
        print("reply      :", result["reply_draft"])
```

运行：

```bash
python -m app.agent.run
```

### 期望结果

| Case | intent | risk_level | 走的路径 | reply 依据 |
|---|---|---|---|---|
| 退款 | 退款进度咨询 | normal | tool_query → evidence | 订单「退款处理中」 |
| 不良反应 | 不良反应 | high | adverse | 高风险处置话术 |
| 物流 | 物流进度 | normal | tool_query → evidence | 物流事实 |

---

## 常见坑速查

1. **节点返回整个 state 而不是 dict 更新** → 返回 `{"字段": 值}` 就好。
2. **list 字段被覆盖** → `evidence` 一定要用 `Annotated[list, add]`，节点只返回新增条目，别原地 `append`。
3. **`route_by_risk` 返回的字符串和映射 key 对不上** → 图会报 `ValueError`。
4. **deepseek-flash 结构化输出** → 只能用 `response_format={"type": "json_object"}`，且 prompt 里必须出现「json」字样；不要用 `with_structured_output` 或 tool calling。
5. **改了 state 字段却没同步 `make_state` 初始值** → TypedDict 缺 key 会报错。
6. **删了 `nodes/risk.py` 但别处还 import** → `tests/test.py` 里 `from app.agent.nodes.risk import risk_node` 要一起改（或直接删掉这个旧的手动脚本，交给 `run.py`）。
