# InsightCopilot（知微客服副驾）

> 面向美妆电商人工客服的全轨迹服务与风险闭环智能体

围绕人工客服工作台，用 Agent 把「识别意图/情绪/风险 → 查业务事实 → 生成可确认的回复草稿 → 高风险升级与承诺跟踪」串成一条可追溯的链路。

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 技术栈](#2-技术栈)
- [3. 项目结构](#3-项目结构)
- [4. 快速开始](#4-快速开始)
- [5. 运行方式](#5-运行方式)
- [6. 环境变量说明](#6-环境变量说明)
- [7. 模型路由与降级](#7-模型路由与降级)
- [8. Agent 流程](#8-agent-流程)
- [9. 数据库](#9-数据库)
- [10. API 接口](#10-api-接口)
- [11. 成本可观测](#11-成本可观测)
- [12. Agent 评测集](#12-agent-评测集)
- [13. 待办 / 路线图](#13-待办--路线图)

## 1. 项目概述

核心能力：

- 多源数据统一关联：客户信息、聊天、订单、工单、事件
- 自动识别用户意图、情绪、风险及缺失信息
- 基于事实证据生成可编辑、可确认的回复草稿
- 不良反应场景的风险判断、信息收集、工单创建与跟进
- 服务承诺自动提取、时间标准化、履约跟踪与逾期提醒
- 高风险操作支持 Human-in-the-loop
- Agent 关键结论可追溯至聊天、订单、工单及业务规则
- 按任务复杂度进行 Fast / Reasoning / Vision 模型路由

## 2. 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12+ / FastAPI / Uvicorn |
| Agent | LangGraph / LangChain / Pydantic |
| 模型 | ChatOpenAI 网关（千问 DashScope / DeepSeek） |
| 存储 | SQLite（SQLAlchemy ORM） |
| 数据 | pandas / openpyxl |
| 质量 | pytest / ruff / mypy |

## 3. 项目结构

```text
InsightCopilot/
├── app/
│   ├── main.py                  # FastAPI 入口（/health + WS /api/chat/stream + __main__ 启动）
│   ├── api/                     # 路由聚合（api_router 统一挂 /api 前缀）
│   │   └── routes/              # cost / health / sessions / customers / orders / tickets / uploads
│   ├── agent/                   # Agent 层
│   │   ├── graph.py             # LangGraph 状态图（节点编排 + 条件边）
│   │   ├── state.py             # CustomerState 共享状态
│   │   ├── run.py               # CLI 入口 + run_copilot / extract_promises
│   │   ├── llm.py               # 结构化 LLM 调用封装（解析器缓存 + 成本记录）
│   │   ├── mock.py              # 确定性 Mock（含否定语规则）
│   │   ├── cost.py              # 成本 / token / 延迟日志（EVA-03）
│   │   ├── time.py              # 中文时间标准化
│   │   ├── nodes/               # 各图节点（intent/emotion/risk/…/fact_check）
│   │   ├── schemas/             # 契约与结构化输出 schema
│   │   └── tools/               # 订单 / 工单查询工具
│   ├── integrations/model/      # 模型网关（fast/reasoning/vision 路由）
│   ├── models/                  # SQLAlchemy ORM（10 张表）
│   ├── prompt/                  # 各节点 prompt 模板
│   ├── schemas/                 # API 层 schema
│   └── core/                    # 数据库连接等基础设施
├── data/
│   ├── sqlite_demo.db           # SQLite 数据库
│   └── annotations.json         # 离线评测金标准标注
├── scripts/                     # 建库 / 导入 / 重置 / 评测脚本
├── tests/                       # 单元测试
├── docs/                        # 设计与任务文档
├── .env.example                 # 环境变量模板
└── pyproject.toml               # 项目配置（ruff/mypy/pytest）
```

## 4. 快速开始

### 4.1 环境要求

- Python **3.12+**（本地 `.venv` 为 3.14，CI 以 3.12 为准）
- 可选：`uv`（`uv.lock` 已提交）

### 4.2 安装依赖

```bash
# 方式一：uv（推荐，锁版本）
uv sync

# 方式二：pip
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 4.3 配置 .env

```bash
cp .env.example .env            # Windows: copy .env.example .env
# 编辑 .env，填入模型 Key（见「环境变量说明」）
```

> 没有模型 Key 也能跑：不配置 Key 时，Agent 会**自动降级到 Mock 结果**，离线演示不受影响。

### 4.4 初始化数据库

```bash
python scripts/init_db.py       # 建 SQLite 库与 10 张核心表
python scripts/import_excel.py  # 导入基线演示数据
```

### 4.5 启动服务

```bash
python app/main.py              # 等价于 uvicorn app.main:app，监听 127.0.0.1:8000
```

### 4.6 验证

```bash
curl http://127.0.0.1:8000/health   # 期望返回 {"status":"ok"}
```

## 5. 运行方式

| 场景 | 命令 |
| --- | --- |
| 启动后端服务 | `python app/main.py` |
| Agent 离线演示（Mock） | `python -m app.agent.run --mock` |
| Agent 演示（真实模型） | `python -m app.agent.run` |
| 只跑某个样例 | `python -m app.agent.run --case 退款` |
| 承诺抽取演示 | `python -m app.agent.run --promise "明天上午给您退款到账"` |
| 打印完整 JSON | `python -m app.agent.run --mock --json` |
| 单元测试 | `python -m pytest tests/ -q` |
| 离线评测 | `python scripts/eval_agent.py [--mock]` |
| 静态检查 | `python -m ruff check . && python -m mypy app` |
| 演示环境重置 | `python scripts/demo_reset.py` |

## 6. 环境变量说明

| 变量 | 说明 | 路由 |
| --- | --- | --- |
| `DASHSCOPE_API_KEY` | 千问（DashScope/百炼）API Key | fast / vision |
| `DASHSCOPE_BASE_URL` | DashScope 兼容模式 base URL | fast / vision |
| `MODEL_FAST` | 快速模型名（如 `qwen-plus`） | fast |
| `MODEL_VISION` | 视觉模型名，缺省走 Mock | vision |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | reasoning |
| `DEEPSEEK_BASE_URL` | DeepSeek base URL | reasoning |
| `MODEL_REASONING` | 推理模型名，缺省回退到 `MODEL_DS` | reasoning |
| `MODEL_DS` | 旧命名，推理模型名 | reasoning |

> 模型名不写死在代码里，全部从 `.env` 读取，便于换模型与现场演示。

## 7. 模型路由与降级

三条路由按任务复杂度分发：

| 路由 | 用途 | 模型 |
| --- | --- | --- |
| `fast` | 意图 / 情绪 / 风险提取等轻量语义任务 | 千问 |
| `reasoning` | 回复生成 / 轨迹摘要等复杂任务 | DeepSeek |
| `vision` | 患处图片 / 批次号识别 | 千问 VL |

三种运行模式（`mode`）：

| 模式 | 行为 |
| --- | --- |
| `mock` | 永远走确定性 Mock，不调用模型，结果可复现 |
| `auto` | 有配置走模型，无配置或调用失败自动降级 Mock |
| `real` | 强制走模型，缺配置或失败直接抛异常（仅开发/评测用） |

## 8. Agent 流程

```text
                         START
                           │
                           ▼
                    ┌─────────────┐
                    │   Context   │
                    │ 加载会话上下文 │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   Intent    │
                    │  意图识别   │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │   Emotion   │
                    │  情绪分析   │
                    └──────┬──────┘
                           ▼
                  ┌─────────────────┐
                  │ Risk Extraction │
                  │  风险信息提取    │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │   Risk Engine   │
                  │  规则定级 L0-L3 │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │   Tool Query    │
                  │  查询订单/工单   │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │    Evidence     │
                  │  事实证据汇总    │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │    Summary      │
                  │  历史轨迹摘要    │
                  └────────┬────────┘
                           │  route_by_risk
              ┌────────────┴────────────┐
          normal (L0)             adverse (L1/L2/L3)
              │                        │
              │                  ┌─────────────┐
              │                  │    Vision    │
              │                  │  图片识别    │
              │                  └──────┬──────┘
              │                         │
              │                  ┌─────────────┐
              │                  │   Adverse    │
              │                  │ 高风险专项处置│
              │                  └──────┬──────┘
              └────────────┬─────────────┘
                           ▼
                    ┌─────────────┐
                    │    Reply    │
                    │  回复草稿生成 │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  Fact Check │
                    │  事实校验    │
                    └──────┬──────┘
                           ▼
                          END
```

节点职责：

| 节点 | 文件 | 类型 | 职责 |
| --- | --- | --- | --- |
| context | `nodes/context.py` | 占位 | V1 不查库，输入由 `CopilotRequest` 预组装 |
| intent | `nodes/intent.py` | LLM(fast) | 意图一级/二级/实体 |
| emotion | `nodes/emotion.py` | LLM(fast) | 情绪 + 情绪趋势 |
| risk_extraction | `nodes/risk_extraction.py` | LLM(fast) | 提取不良反应/症状/就医/监管投诉 |
| risk_engine | `nodes/risk_engine.py` | 纯代码 | 规则判定 L0-L3 |
| tool_query | `nodes/tool_query.py` | 工具 | 关键词命中 → 查订单/工单 |
| evidence | `nodes/evidence.py` | 纯代码 | 业务事实压成证据（可追溯） |
| summary | `nodes/summary.py` | LLM(reasoning) | 历史轨迹摘要 |
| vision | `nodes/vision.py` | LLM(vision) | 患处图片/批次号识别 |
| adverse | `nodes/adverse.py` | 纯代码 | 高风险专项：补问缺失字段、生成工单草稿 |
| reply | `nodes/reply.py` | LLM(reasoning) | 基于意图+情绪+证据生成回复草稿 |
| fact_check | `nodes/fact_check.py` | 纯代码 | 校验草稿事实是否在证据中，高风险可拦截 |

风险分级：**L0** 普通接待；**L1-L3** 不良反应专项（按症状严重度 + 是否就医 + 监管投诉分级）。

## 9. 数据库

SQLite，连接串 `sqlite:///./data/sqlite_demo.db`（见 `app/core/database.py`），10 张表：

| 表 | 说明 |
| --- | --- |
| `consumer` | 消费者（脱敏展示名 + 昵称哈希） |
| `service_session` | 服务会话 |
| `message` | 聊天消息 |
| `sales_order` | 订单 |
| `service_ticket` | 工单 |
| `service_event` | 时间线事件 |
| `promise` | 服务承诺 |
| `ai_analysis` | Agent 分析结果（含成本日志落库） |
| `action_execution` | 动作执行记录 |
| `audit_log` | 审计日志 |

## 10. API 接口

> 全部接口统一返回 `{data, meta, error}` 信封；Base URL 为 `/api`（WebSocket 与测试接口除外）。

### 已实现（已挂载）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/health` | 健康检查 |
| GET | `/api/health` | 健康检查（带 DB 探活） |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/{id}` | 会话详情 |
| GET | `/api/sessions/{id}/messages` | 会话消息列表 |
| POST | `/api/sessions/{id}/messages` | 发送 / 草稿消息（支持图片附件 `attachment`） |
| GET | `/api/customers/{id}` | 客户详情（脱敏展示名） |
| GET | `/api/customers/{id}/timeline` | 客户时间线 |
| GET | `/api/orders` | 订单列表 |
| GET | `/api/orders/{id}` | 订单详情 |
| GET | `/api/products` | 商品库（公司产品信息；按品类筛选，默认在售）——售前推荐的事实来源 |
| GET | `/api/tickets` | 工单列表 |
| GET | `/api/tickets/{id}` | 工单详情 |
| POST | `/api/tickets` | 创建工单（如不良反应/退款专项工单，从 `draft_payload` 预填） |
| PATCH | `/api/tickets/{id}` | 更新工单 |
| GET | `/api/promises` | 服务承诺队列（履约雷达数据源；按状态/截止/风险筛选） |
| POST | `/api/promises/extract` | 从一条客服已发送消息抽取并落库承诺（无承诺返回 `created=false`） |
| POST | `/api/promises/scan` | 即时重算承诺 `due_soon` / `overdue`（演示用，不依赖真实等待） |
| PATCH | `/api/promises/{id}` | 承诺状态流转（确认 / 变更 / 履约 / 取消 / 升级） |
| POST | `/api/actions/preview` | 高影响动作预览（不落库，返回将产生的副作用描述） |
| POST | `/api/actions/confirm` | 确认执行动作（幂等：带 `idempotency_key`，重复提交返回同一结果） |
| GET | `/api/risk-queue` | 风险队列：主管视角的会话 / 工单 / 承诺聚合 |
| POST | `/api/demo/reset` | 一键恢复 `baseline-v1` 固定演示数据（工程验收：3 秒内可重置） |
| POST | `/api/uploads` | 上传照片 / 附件（multipart `file` + `kind=image\|attachment`），校验扩展名白名单 + 体积上限，返回 `/media/...` 可访问 URL |
| GET | `/api/cost/summary` | 全局成本汇总（token / 金额 / 按路由拆分） |
| GET | `/api/cost/{session_id}` | 单会话成本明细 |
| GET | `/api/cost/consumer/{consumer_id}` | 单用户成本累计（该用户所有会话合并） |

### 实时 / 测试接口（定义在 `app/main.py`，不走 `/api` 前缀）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| WS | `/api/chat/stream/{session_id}` | 买家消息 → LangGraph 流式分析；按 `session_id` 从数据库加载真实消息/订单/工单/时间线，回复落库后自动抽取服务承诺并广播 `promise`；售前咨询会按肤质匹配在售商品作为推荐证据；会话结束回传 `cost_summary` 帧 |
| POST | `/api/test/buyer_message` | 模拟买家消息，跑一次副驾分析并广播（仅本地联调，不落库） |

### 静态资源

| 路径 | 说明 |
| --- | --- |
| `/media/<file>` | 上传文件静态访问（对应 `/api/uploads` 落盘的 `data/media/`） |

### 规划中 / 暂未挂载

- 副驾 HTTP 接口 `/api/sessions/{id}/copilot` 与 SSE 流（在 `deprecated_agent.py`，未挂载，等待重构；能力已由 WS `/api/chat/stream/{id}` 覆盖）
- 承诺抽取与建单的「预览 → 确认」前端交互面板（后端 `POST /api/actions/preview|confirm` 已就绪，前端履约雷达当前只读展示 + 模拟扫描）

> 说明：服务承诺跟踪（`/api/promises`、`/api/actions`）、风险队列（`/api/risk-queue`）、演示重置（`/api/demo/reset`）与工单创建（`POST /api/tickets`）均已实现并挂载；前端履约雷达 `RadarView` 已接真实 `/api/promises` 数据。

## 11. 成本可观测

比赛把「模型性能与成本优化能力」列为加分项，本质是看 **是否有 token 节约机制 + 能否体现消耗**。本项目用**日志替代复杂可视化**，且按用户决策**不新增成本导航页**。

### 怎么看到 AI 成本

- 前端：每条 WebSocket 会话结束时，后端在 `finally` 回传 `cost_summary` 帧，前端弹窗提示
  `本次 AI 消耗 ¥x（n 次调用 / 共 m tokens，降级 p%）`。
- 后端接口（进程内累计，演示期间单进程常驻即可）：
  - `GET /api/cost/summary` —— 全局汇总 + 按路由（triage / reply / …）拆分，便于对比合并前后的降本收益。
  - `GET /api/cost/{session_id}` —— 单会话明细（每次模型调用的 route / model / token / 成本）。
  - `GET /api/cost/consumer/{consumer_id}` —— 单用户累计（该消费者名下所有会话的成本合并）。

### 降本机制（可量化）

- **意图 / 情绪 / 风险合并**：`triage` 节点把三件事合并成 1 次模型调用（fast 路由）。
- **空历史跳过模型**：`summary` 节点在无历史轨迹时跳过模型调用，直接走 Mock（省 1 次 reasoning 路由调用）。
- 因此默认对话流通常只有 **2 次真实调用**（triage + reply），其余走规则 / Mock。

### 成本计算与限制

- 单价见 `app/agent/cost.py` 的 `MODEL_PRICING`（按模型 input / output 每百万 token 单价）；金额用浮点 `compute_cost_yuan`（保留 6 位小数），Mock / 降级调用不计费（`cost_yuan = 0`）。
- 成本日志为**进程内内存**（不落库），单进程常驻才累计；服务重启会清零。演示场景足够；若要持久化可改为落 `ai_analysis` 表或外部时序库。

## 12. Agent 评测集

为量化 Agent 的「分类准确性 + 风险召回 + 回复质量 + 成本效率」，项目内置了一个轻量评测 Harness（纯 Python，不依赖前端，与第 11 节成本可观测同源）。

### 文件

| 文件 | 作用 |
| --- | --- |
| `eval/eval_cases.jsonl` | 评测用例集（JSONL，一行一条）。字段直接复用 `TriageAnalysis` 真实枚举（`intent_primary` / `emotion` / `risk` / `entities`）与回复 rubric（`must_contain` / `must_not` / `brand_compliance`） |
| `eval/run_eval.py` | 评测运行器：直接 `graph.invoke(...)` 拿完整 final state（含 triage 原始 `risk` 全字段 + `reply_draft`），再用 `cost.session_totals` 取成本；四维度评分；LLM 裁判做成 `--judge` 可选开关 |
| `eval/report.md` | 主基准报告（比赛给定的 6 条，运行后自动生成） |
| `eval/dev_cases.jsonl` | 内部扩展集（8 条，覆盖 6 条未涉及的场景：物流单号、价格、使用不当、竞品对比、平台投诉、严重症状、退换货、复购），用于压测泛化、避免对 6 条过拟合 |
| `eval/report_dev.md` | 扩展集报告（用 `--in-file eval/dev_cases.jsonl --out eval/report_dev.md` 生成） |

用例格式示例：

```json
{
  "id": "EVAL-001",
  "category": "不良反应",
  "difficulty": "hard",
  "consumer_id": "C00005",
  "input": "用了你们家精华全脸红肿起疹子,痒得睡不着,是不是过敏了?",
  "expected": {
    "intent_primary": "不良反应",
    "emotion": "焦虑",
    "risk": { "adverse_reaction": true, "severity": "obvious", "medical_visit": false, "regulatory_complaint": false },
    "entities": ["精华"],
    "reply_rubric": { "must_contain": ["停用", "安抚", "就医建议"], "must_not": ["诊断", "保证治愈"], "brand_compliance": true }
  }
}
```

多轮上下文 / 带订单场景可用 `setup.messages`、`setup.orders` 字段构造。

### 四个评测维度

| 维度 | 评分方式 | 对标字段 |
| --- | --- | --- |
| 意图 / 情绪分类 | `intent_primary` / `emotion` 精确匹配；`entities` 用**包含匹配 F1**（细粒度命中粗粒度也算中，缓解金标准粒度不一致） | `intent_primary`, `emotion`, `entities` |
| 风险召回（安全） | `adverse_reaction` / `medical_visit` / `regulatory_complaint` 必须不漏；`severity` 用序数精度（none < mild < obvious < severe） | `risk` 全字段 |
| 回复质量 | 规则校验 `must_contain` / `must_not`；加 `--judge` 后由 deepseek-flash 按 1–5 评品牌合规 / 共情 / 准确 / 可操作 | `reply_draft.reply` |
| 成本效率 | 直接读 `cost_summary`：平均 token、调用次数、降级占比 | 已落地的成本接口 |

> 前两项为确定性打分（不依赖 LLM 裁判），可稳定复现；成本维度与第 11 节同源，正好证明降本可量化。

### 运行

```bash
uv run python eval/run_eval.py                 # 全量跑，出 report.md
uv run python eval/run_eval.py --limit 2        # 只跑前 2 条
uv run python eval/run_eval.py --cases 不良反应  # 按 category 关键词过滤
uv run python eval/run_eval.py --judge          # 开启 LLM 裁判（会消耗 token）
```

### 基线参考（主基准 · 比赛 6 条）

- 风险召回 overall = **1.0**（未漏判任何不良反应 / 就医 / 监管威胁）
- 意图准确率 **1.0**、情绪准确率 0.833、实体 F1 **0.833**（实体抽取经优化后由 0.444 提升）
- 综合质量分 **0.884**；平均 **2627 tokens / 用例**，每用例仅 **2 次真实调用**（印证降本设计）

### 评测集覆盖策略

比赛给定的 6 条是**锁定基准**，直接用于对外汇报 / 比赛评分，**不要为刷分针对这 6 条过拟合**（那样在隐藏 / 扩充样本上会塌）。为验证「真实泛化能力」而非「凑巧得分」，另设内部扩展集 `eval/dev_cases.jsonl`（8 条，覆盖 6 条未涉及的场景：物流单号、价格咨询、使用不当、竞品对比、平台投诉、严重症状、退换货、复购），单独跑：

```bash
uv run python eval/run_eval.py --in-file eval/dev_cases.jsonl --out eval/report_dev.md
```

扩展集结果（截至最近一次优化）：意图 1.0、实体 F1 1.0、风险召回 0.984 —— 说明实体 / 意图 / 订单上下文等通用增强在未见场景上同样成立，而非只过拟合 6 条。扩展集的 `expected` 由我们自行标注，跑出 low-score 时优先复查「金标准是不是写错了」（评测集的价值之一就是测标注质量）。

迭代闭环：针对 low-score case 修改 prompt / 节点 → 重跑 → 看提升。

## 13. 待办 / 路线图

- [ ] 接线副驾 HTTP 接口（`/api/sessions/{id}/copilot` 等，`deprecated_agent.py` 重构后挂载）
- [x] 前端（React + TypeScript + Vite，目录 `InsightCopilot-frontend/`，已接入 WS 与上传）
- [ ] 真实 Excel 数据导入
- [ ] README 一键启动脚本（任务 P-01）
- [ ] 现场离线部署 + 断网降级演示验收
