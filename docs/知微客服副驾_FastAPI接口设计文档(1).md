# 知微客服副驾 FastAPI 接口设计文档

**版本**：v0.1（初赛 Demo 后端准备）  
**日期**：2026-09-13  
**状态**：开发契约草案

## 1. 接口范围

接口围绕客服工作台三栏布局和履约雷达设计，首期后端使用 SQLite + FastAPI，数据来自已脱敏的 Excel 导入库；百炼模型不可用时返回结构化 Mock 结果。接口先满足浏览器演示，后续可在不改变核心资源模型的情况下切换 PostgreSQL 和真实模型。

本阶段覆盖：会话队列、会话详情、消费者时间线、订单事实、工单事实、Agent 副驾、动作预览/确认、服务承诺队列、承诺抽取/扫描和 Demo 重置。

## 2. 全局约定

### 2.1 请求与响应

- Base URL：`/api`。暂不增加版本前缀；正式部署可通过网关映射到 `/api/v1`。
- Content-Type：`application/json; charset=utf-8`。
- 时间：RFC3339，例如 `2026-09-13T10:30:00+08:00`；数据库统一 UTC。
- 金额：接口返回整数分字段（如 `paid_amount_cent`），同时可返回只读格式化字段 `paid_amount_display`。
- 分页：列表接口使用 `page`（默认 1）和 `page_size`（默认 20，最大 100）；响应 `meta.total`。
- 所有请求可携带 `X-Request-ID`；未提供时由服务生成并在响应中返回。
- Demo 操作员通过 `X-Operator-ID` 标识；当前只做最小鉴权占位，不能视为生产权限系统。

成功响应统一为：

```json
{
  "data": {},
  "meta": {"request_id": "req_01", "page": 1, "page_size": 20, "total": 138},
  "error": null
}
```

失败响应统一为：

```json
{
  "data": null,
  "meta": {"request_id": "req_01"},
  "error": {"code": "SESSION_NOT_FOUND", "message": "会话不存在", "details": {}}
}
```

### 2.2 脱敏与证据

- API 不返回支付宝账号、支付宝实名、手机号、详细地址或物流号原值；只能返回掩码或“已隐藏”。
- `source_type` + `source_id`、`evidence_message_ids` 是所有 Agent 结论的证据入口。
- 草稿消息不触发正式承诺；只有 `POST /api/sessions/{id}/messages` 的最终发送消息才能进入承诺抽取链路。
- 所有高影响动作必须先预览再确认，预览接口不得改变订单、工单或承诺状态。

## 3. 资源与 Pydantic 契约

下面是实现时应落地的核心模型（字段可扩展，不可删除或改变语义）：

```python
class SessionListItem(BaseModel):
    session_id: str
    customer_id: str
    customer_name_masked: str
    store_name: str
    scene_major: str | None
    scene_minor: str | None
    last_message_at: datetime
    risk_level: Literal["L0", "L1", "L2", "L3"]
    emotion: str
    unresolved_count: int
    open_ticket_count: int
    active_promise_count: int


class EvidenceRef(BaseModel):
    source_type: Literal["chat", "order", "ticket", "rule", "action"]
    source_id: str
    message_id: str | None = None
    quote: str | None = None  # 脱敏短引文


class CopilotInsight(BaseModel):
    intent_primary: str | None
    intent_secondary: str | None
    emotion: str
    risk_level: Literal["L0", "L1", "L2", "L3"]
    risk_reasons: list[str]
    missing_fields: list[str]
    suggested_actions: list[str]
    evidence: list[EvidenceRef]
    model_route: Literal["fast", "reasoning", "vision", "mock"]
    degraded: bool = False


class ActionPreviewRequest(BaseModel):
    session_id: str
    action_type: Literal["CREATE_TICKET", "ESCALATE", "FOLLOW_UP", "NUDGE_TICKET", "CREATE_PROMISE", "MARK_FULFILLED"]
    draft_payload: dict[str, Any]
    source_message_id: str | None = None


class ActionConfirmRequest(BaseModel):
    action_id: str
    idempotency_key: str = Field(min_length=8, max_length=128)
    payload: dict[str, Any] | None = None


class PromisePatch(BaseModel):
    status: Literal["active", "due_soon", "overdue", "fulfilled", "changed", "cancelled"] | None = None
    due_at: datetime | None = None
    owner_id: str | None = None
    verification_type: str | None = None
    verification_ref: str | None = None
    reason: str | None = None


class PromiseExtractRequest(BaseModel):
    session_id: str
    message_id: str
    message_text: str
    mode: Literal["model", "mock", "auto"] = "auto"
```

## 4. 接口清单与行为

### 4.1 基础与会话

#### `GET /api/health`

返回服务、数据库和模型网关状态。字段：`status`、`database`、`model_provider`、`version`、`server_time`。数据库不可用时返回 HTTP 503。

#### `GET /api/sessions`

会话队列，支持筛选和分页。

Query 参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` / `page_size` | int | 分页；最大 100 |
| `q` | string | 脱敏昵称、会话 ID、场景关键词 |
| `risk_level` | `L0-L3` | 风险筛选 |
| `status` | `open/closed/pending` | 会话状态 |
| `scene_major` | string | 主场景 |
| `has_open_promise` | bool | 是否有未完成承诺 |
| `sort` | `last_message_at/risk` | 默认最近消息优先 |

响应 `data.items: SessionListItem[]`。默认排序：L3/L2 优先，其次 `last_message_at DESC`。不得把原始昵称作为搜索回显。

#### `GET /api/sessions/{session_id}`

返回会话聚合详情：

```json
{
  "session": {"session_id": "S00015", "customer_name_masked": "魏h**", "risk_level": "L3"},
  "messages": [],
  "orders": [],
  "tickets": [],
  "events": [],
  "promises": [],
  "copilot": {"insight": {}, "draft_reply": null, "generated_at": null}
}
```

消息默认按 `seq_no ASC`，事件按 `occurred_at ASC`。可选 `include=analysis,events,promises`，服务端仍必须做权限和脱敏过滤。

#### `GET /api/sessions/{session_id}/copilot`

触发或读取当前会话 Agent 结果。默认 `mode=auto`：有可用百炼时走模型，否则走规则/Mock。Query：`mode=auto|fast|reasoning|vision|mock`、`refresh=false|true`。

响应包含 `CopilotInsight`、`draft_reply`、`analysis_id`、`evidence`、`model_route`、`degraded`。生成前必须查询关联订单和工单，不得猜金额、状态或时间；结果写入 `ai_analysis`，不改变业务状态。

#### `POST /api/sessions/{session_id}/messages`

模拟客服最终发送消息或追加系统消息，供承诺抽取和时间线使用。

请求：`{"role":"agent","content":"...","send":true,"client_message_id":"..."}`。

当 `send=true` 时写入 `message` 和 `service_event`，随后异步调用 `POST /api/promises/extract`；草稿保存使用 `send=false`，不能生成正式承诺。返回 `message_id`、`event_id` 和 `promise_extract_job_id`。

#### `GET /api/sessions/{session_id}/stream`

SSE 推送 Agent 生成、动作执行和承诺状态变化。事件名：`analysis.started`、`analysis.delta`、`analysis.completed`、`action.completed`、`promise.updated`、`error`。每条事件包含 `request_id` 和 `session_id`。前端断线用 `Last-Event-ID` 重连；没有异步任务时可返回 keep-alive。

### 4.2 消费者、订单和工单

#### `GET /api/customers/{customer_id}/timeline`

跨会话、订单和工单的统一时间线。

Query：`from`、`to`、`event_type`、`page`、`page_size`。响应 `items` 中每项包含 `event_id`、`occurred_at`、`title`、`content`、`source_type`、`source_id`、`evidence_message_ids`。只返回该消费者的脱敏视图；事件顺序按时间倒序用于主管看板，详情页可传 `order=asc`。

#### `GET /api/orders/{order_id}`

返回订单事实：商品、数量、金额分、订单状态、赠品、快递公司、脱敏物流号、省市和买家留言摘要，以及关联会话/工单 ID。不存在返回 `404 ORDER_NOT_FOUND`。金额和状态来自数据库，不经过模型改写。

#### `GET /api/tickets/{ticket_id}`

返回统一工单核心字段与按 `ticket_type` 校验后的 `detail`。`offline_payment` 仅返回 `alipay_name_masked`、`alipay_account_masked` 和金额分；`adverse_reaction` 返回症状摘要、停用/就医状态和回访状态，不返回诊断结论。可选 `include=events`。

#### `GET /api/risk-queue`

主管风险队列的便捷接口，等价于会话、工单和承诺的聚合查询。参数：`risk_level`、`ticket_type`、`status`、`page`、`page_size`。返回 `risk_reasons` 和证据引用，便于右侧风险卡直接渲染。

### 4.3 动作预览与确认

#### `POST /api/actions/preview`

生成可编辑的动作草稿，不写入业务状态。

请求示例：

```json
{
  "session_id": "S00015",
  "action_type": "CREATE_TICKET",
  "source_message_id": "m-1001",
  "draft_payload": {
    "ticket_type": "adverse_reaction",
    "priority": "urgent",
    "symptom_summary": "面部泛红和刺痛",
    "sought_medical_help": false,
    "follow_up_due_at": "2026-09-14T10:00:00+08:00"
  }
}
```

响应包含 `action_id`、标准化 `payload`、缺失字段、风险提示、证据、`expires_at`（建议 10 分钟）和 `requires_confirmation=true`。校验失败返回 `422 ACTION_PAYLOAD_INVALID`。

#### `POST /api/actions/confirm`

执行已预览动作。必须携带 `X-Operator-ID`、`idempotency_key`，并校验预览未过期、会话和字段版本未变化。

成功响应：`action_id`、`status=executed`、`result_ticket_id`、`result_promise_id`、`events[]`。同一幂等键再次请求返回原执行结果，不重复建单。版本冲突返回 `409 VERSION_CONFLICT`；未预览或已过期返回 `409 ACTION_PREVIEW_REQUIRED`。

动作副作用：

| 动作 | 结果 |
| --- | --- |
| `CREATE_TICKET` | 创建/更新 `service_ticket`，写入 `service_event` 和审计 |
| `ESCALATE` | 提升风险/优先级，写入升级事件，不自动退款 |
| `FOLLOW_UP` | 创建回访承诺，状态为 `pending_confirmation` 或 `active` |
| `NUDGE_TICKET` | 写入催办事件，保留工单原状态 |
| `CREATE_PROMISE` | 创建经人工确认的服务承诺 |
| `MARK_FULFILLED` | 按验证规则检查证据后履约，不允许无证据强制关闭 |

所有副作用在一个数据库事务中完成。

### 4.4 服务承诺

#### `GET /api/promises`

承诺队列和履约雷达数据。

Query：`status`（可重复）、`risk_level`、`owner_id`、`session_id`、`due_before`、`page`、`page_size`、`include=verification`。

返回 `items`，每项包含 `promise_id`、`session_id`、`customer_name_masked`、`promise_type`、`statement`、`due_at`、`status`、`remaining_seconds`、`owner_id`、`source_message_id`、`verification`、`evidence`。`remaining_seconds` 由服务端当前时间计算，负数表示超时。

#### `POST /api/promises/extract`

从最终客服消息抽取候选承诺。请求使用 `PromiseExtractRequest`。仅返回候选，不自动生效：

```json
{
  "candidate": {
    "promise_type": "follow_up",
    "statement": "明天上午回访进展",
    "due_at": "2026-09-14T12:00:00+08:00",
    "owner_type": "agent",
    "confidence": 0.92,
    "evidence": [{"source_type": "chat", "source_id": "m-1002", "message_id": "m-1002"}]
  },
  "needs_confirmation": false,
  "model_route": "mock"
}
```

模糊表达（如“尽快”“稍后”）必须返回 `needs_confirmation=true` 且 `due_at=null`，由人工通过动作确认。解析“3 个工作日”和“72 小时”使用同一时间服务但语义不同，节假日规则保存在配置表。

#### `PATCH /api/promises/{promise_id}`

支持确认、改期、分派、履约和取消。请求体为 `PromisePatch`，必须携带 `X-Operator-ID` 和 `If-Match: <version>`。状态迁移不符合状态机返回 `409 PROMISE_TRANSITION_INVALID`。

履约时服务端按 `verification_type` 查询工单、订单或消息证据，自动写 `fulfilled_at`、`evidence_event_id` 和时间线事件；不能只靠前端传 `status=fulfilled`。

#### `POST /api/promises/scan`

立即执行一次承诺扫描，供 Demo 按钮使用。请求可选 `now`（仅 Mock/测试环境允许）和 `dry_run`。扫描 `active` 承诺并更新 `due_soon`/`overdue`，返回 `changed_count` 和变更项。生产环境禁止客户端伪造 `now`。

### 4.5 Demo 管理

#### `POST /api/demo/reset`

恢复固定初始数据，默认场景包括退款、不良反应和赠品补发。请求：

```json
{"scenario": "all", "seed": "baseline-v1", "preserve_import": true}
```

服务端在事务中清理演示生成的动作、分析、事件和承诺，恢复 baseline；返回 `reset_id`、`scenario`、`restored_at`、`counts` 和 `duration_ms`。目标小于 3 秒，失败完整回滚。

## 5. 错误码

| HTTP | code | 场景 |
| ---: | --- | --- |
| 400 | `INVALID_PARAMETER` | 查询参数或 JSON 格式错误 |
| 401/403 | `UNAUTHORIZED` / `FORBIDDEN` | 缺少操作员或无权限 |
| 404 | `SESSION_NOT_FOUND`、`ORDER_NOT_FOUND`、`TICKET_NOT_FOUND`、`PROMISE_NOT_FOUND` | 资源不存在 |
| 409 | `VERSION_CONFLICT`、`ACTION_PREVIEW_REQUIRED`、`PROMISE_TRANSITION_INVALID`、`IDEMPOTENCY_CONFLICT` | 状态/版本/幂等冲突 |
| 422 | `ACTION_PAYLOAD_INVALID`、`MISSING_REQUIRED_FIELD` | 业务字段校验失败 |
| 429 | `RATE_LIMITED` | 模型或接口限流 |
| 503 | `DATABASE_UNAVAILABLE`、`MODEL_UNAVAILABLE` | 依赖暂不可用 |

模型超时、配额不足或断网时，业务接口仍返回 HTTP 200 的 `degraded=true` Mock 结果；只有数据库不可读写时才阻断写操作。

## 6. FastAPI 分层建议

```text
app/
  main.py                 # FastAPI app、异常处理、中间件
  api/routes/             # sessions、customers、orders、tickets、actions、promises、demo
  schemas/                # Pydantic 请求/响应
  services/               # session、ticket、promise、action、timeline
  agents/                 # ModelGateway、MockProvider、提示词和结构化解析
  db/                     # SQLAlchemy models、Alembic、seed/import/reset
  core/                   # 配置、鉴权占位、脱敏、时间和错误码
```

路由层只做参数和权限校验；服务层负责状态机和事务；Agent 层只产出结构化候选；工具/服务层查询订单、工单和规则事实。模型不得直接写数据库。

## 7. 关键流程

### 7.1 客服副驾

```text
打开会话 -> GET /sessions/{id}
         -> GET /sessions/{id}/copilot
         -> 展示洞察/证据/草稿
         -> 客服编辑 -> POST /sessions/{id}/messages(send=true)
         -> POST /promises/extract -> 人工确认 -> PATCH /promises/{id}
```

### 7.2 不良反应

```text
L2/L3 识别 -> actions/preview(CREATE_TICKET)
          -> 人工补齐症状/停用/就医字段
          -> actions/confirm
          -> 生成 adverse_reaction 工单 + 回访 promise + 时间线事件
```

### 7.3 履约雷达

```text
GET /promises -> POST /promises/scan -> GET /promises(status=due_soon,overdue)
             -> 业务完成后 PATCH /promises/{id}(fulfilled)
             -> 服务端验证证据并更新 service_event
```

## 8. 安全、可观测性与测试验收

- 请求日志包含 `request_id`、路由、状态码、耗时和 `operator_id`，不记录原始敏感值和完整模型上下文。
- 对写接口增加简单限流；生产部署再接 JWT/RBAC，按店铺和处理人过滤数据。
- Agent 日志记录路由、耗时、Token、错误、Mock 降级原因和人工修改前后差异。
- 所有写接口覆盖：成功、参数校验、重复幂等键、并发版本冲突、数据库回滚测试。
- 关键端到端验收：`S00015` 不良反应建单与回访、退款场景承诺、赠品补发催办；重置后结果一致。
- 数据验收：API 不出现支付宝/手机号/地址原值；会话详情能追溯到聊天、订单、工单或规则证据。
- 性能目标：普通会话副驾 P95 < 3 秒；复杂跨源查询 P95 < 6 秒；承诺扫描不阻塞在线接待。

## 9. 暂定决策与后续兼容

1. 首期资源路径保持 `/api/...`，上线前若需要版本化，只新增 `/api/v1` 网关别名。
2. 首期五类工单使用统一 `detail` JSON + 白名单校验；真实业务稳定后可迁移为一对一扩展表。
3. 首期异步任务使用 FastAPI `BackgroundTasks` 或 APScheduler；数据量扩大后再替换 Celery/Redis。
4. 本文不锁定百炼具体模型名称，模型从环境变量读取；`mock` 路由始终保留，保证断网可演示。
