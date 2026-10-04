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
- [11. 待办 / 路线图](#11-待办--路线图)

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
│   ├── main.py                  # FastAPI 入口（/health + __main__ 启动）
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

当前实现：

| 方法 | 路径 | 状态 |
| --- | --- | --- |
| GET | `/health` | ✅ 已实现 |

规划中（对照 `docs/知微客服副驾_FastAPI接口设计文档`，尚未接线）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/{id}` | 会话详情 |
| GET | `/api/sessions/{id}/copilot` | **副驾核心接口**（调 `run_copilot`） |
| POST | `/api/sessions/{id}/messages` | 发送/草稿消息 |
| GET | `/api/sessions/{id}/stream` | 流式输出 |
| GET | `/api/customers/{id}/timeline` | 客户时间线 |
| GET | `/api/orders/{id}` / `/api/tickets/{id}` | 订单/工单详情 |
| GET | `/api/risk-queue` | 风险队列 |
| POST | `/api/actions/preview` / `/api/actions/confirm` | 动作预览/确认 |
| GET/POST/PATCH | `/api/promises...` | 承诺抽取/扫描/更新 |
| POST | `/api/demo/reset` | 演示重置 |

## 11. 待办 / 路线图

- [ ] 接线副驾 HTTP 接口（`/api/sessions/{id}/copilot` 等）
- [ ] 前端（React + TypeScript + Vite，任务 P-02）
- [ ] 真实 Excel 数据导入
- [ ] README 一键启动脚本（任务 P-01）
- [ ] 现场离线部署 + 断网降级演示验收
