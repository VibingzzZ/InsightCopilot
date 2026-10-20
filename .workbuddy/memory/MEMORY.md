# 项目长期约定（InsightCopilot）

## 前端
- 真实前端是 Vite + React + TS（目录 `InsightCopilot-frontend/`），**不是单文件页**。联调/演示用 `npm run dev`（默认 5173）。
- 前端 WS 连的是 `ws://localhost:8000/api/chat/stream/{conversationId}`（`src/services/socket.ts`）。**这就是"现有 WebSocket 路由"**，升级它，不要另起路径。
- CORS：`config.CORS_ALLOW_ORIGINS = ['http://localhost:5173','http://127.0.0.1:5173']`（可由环境变量 `CORS_ALLOW_ORIGINS` 覆盖）。**非这两个源的 WS/请求会被 403**（含 `null`/测试客户端）。前端跑在 5173 才放行。
- 草稿渲染走 `useChatStore`（key=`drafts[conversationId]`）；副驾面板在 `src/features/Copilot/CopilotPane.tsx`。

## 后端
- 入口 `app/main.py`。路由聚合在 `app/api/routes/`（业务接口带 `/api` 前缀）；`/health` 与 `/api/chat/stream/{id}`、`/api/test/buyer_message` 直接在 `app` 上。
- 指令契约：`app/schemas/commands.py`（`parse_command` + `CommandError` 容错）。轻量改写：`app/agent/rewrite.py` + `app/prompt/rewrite.py`，复用 `run_structured`，绕过查单/风险/事实重流程。
- Gateway 占位 Key（中文"你的百炼key"）必须视为不可用 → Mock 降级（`app/integrations/model/gateway.py` 的 `_key_usable`）。否则 OpenAI 客户端抛 UnicodeEncodeError。
- **FastAPI 端点函数名禁止以 `test_` 开头**（路由路径可含 `test/`），否则 pytest 误当测试收集报 `fixture 'payload' not found`。跑测试只针对 `tests/` 目录。

## 文件上传（照片/附件）
- 新增上传端点 `POST /api/uploads`（multipart：`file` + `kind=image|attachment`），落盘到 `data/media/`，经 `StaticFiles` 挂载的 `/media` 静态可访问（见 `app/api/routes/uploads.py` + `config.UPLOAD_DIR`）。
- 校验：扩展名白名单（`config.IMAGE_EXTENSIONS`/`ATTACHMENT_EXTENSIONS`）+ 体积上限（`config.MAX_UPLOAD_SIZE_MB`，默认 10MB）；非法扩展名返 415，超限 413。文件名用 uuid 重命名，返回 `{url,path,original_name,...}`（统一信封 `ok`）。
- **依赖 `python-multipart`**（FastAPI `UploadFile` 必需，已 `uv add` 写入 pyproject/requirements）。
- 消息带附件：`SessionMessageCreateRequest` 增 `attachment`(path/url) + `attachment_kind`；`append_message` 在 kind=image 时写 `image_path` 并置 `content_type='image'`（`app/services/session_service.py`）。
- 前端：`src/services/upload.ts` 负责上传；`Workspace.tsx` 两个占位按钮已接通（选文件→上传→待发送预览→随消息发出）；`MessageBubble`/`Overlay` 真实渲染图片与文件卡片。前端 API base 写死 `http://localhost:8000`。

## 成本可观测（赛题加分项：模型性能与成本优化能力）
- 赛题只要求"能看到 AI 成本 + 降本机制可量化"，演示用**日志替代**复杂可视化；用户决策"成本入口不做"（不新增侧边栏导航页）。
- 设计：①每条 WS 会话结束时后端在 `finally` 推 `cost_summary` 帧（含 `cost_yuan` 浮点/`cost_yuan_display`/`total_tokens`/`calls`/`degraded`），前端 `src/services/socket.ts` 收到后弹"本次 AI 消耗 ¥x（n 次调用 / 共 m tokens，降级 p%）"；②全局 `GET /api/cost/summary`（按路由聚合）；③单会话 `GET /api/cost/{id}`；④单用户 `GET /api/cost/consumer/{consumer_id}`（从 `ServiceSession` 取该用户 session 列表，再用 `cost.rollup` 合并内存日志）。
- 金额换算：`app/agent/cost.py` 的 `MODEL_PRICING`（按模型 input/output 每百万 token 单价）+ `compute_cost_yuan`（**浮点 round 6 位**，不要 int 分，否则单次 ¥0.002 被舍成 0）。`record_call` 的 `cost_yuan` 在 `degraded=True` 时强制 0（Mock 不计费）。
- 降本设计：triage 合并 intent+emotion+risk 为 1 次调用；summary 无历史时跳过模型走 mock。所以默认流通常只有 2 次真实调用（triage+reply），属正常。
- **活动节点（triage/summary/reply/vision）调 `run_structured` 必须显式传 `session_id=state.get("session_id")`**——contextvars 在异步 LangGraph 跑同步节点时会丢，不传则成本归属不到会话。
- 成本日志为**进程内内存**（`cost.py` 的 `ModelCallRecord` 列表），单进程常驻才累计；重启清零（符合"日志替代"方案）。`consumer` 聚合只能统计同一进程内跑过的会话。
- **坑**：`cost_consumer` 曾因 `session_ids = [s.session_id for s in db.scalars(...).all()]` 把 scalars 字符串当对象取属性而 500；正确写法是 `list(db.scalars(...).all())`（scalars 直接返回 session_id 字符串列表）。

## 工作流坑
- 残留 uvicorn 进程：Git Bash 的 `taskkill //F //PID` 会被吞掉静默失败；改用 **PowerShell `Stop-Process -Force -Id <pid>`** 才能杀掉。杀前先用 `netstat -ano | grep :8000` 找 pid。固定代码必须跑在 **8000**（前端 socket.ts 硬编码），别用临时端口绕。
- 改造性未提交改动易被工作树重置吃掉；对已有文件的编辑要连同新文件一起提交。
- Git Bash 下 `/tmp` 会解析成 Windows `C:\tmp`，导致 curl `-F @/tmp/x`、`--data @/tmp/x` 找不到文件；测试文件请放在项目目录内。
- **CI 跑 `uv run ruff check .`**：FastAPI 路由参数里的 `File()`/`Form()`/`Depends()` 必须写成 `Annotated[X, File()]` 形式（写在默认值位会被 B008 判错导致 CI 挂）。`uploads.py` 的 `upload_file` 已改为 Annotated 风格，新增/改签名时照此写。

## Agent 评测集（Harness 骨架）
- 位置：`eval/`（非 `tests/`，避免 pytest 收集；文件名非 `test_` 开头；`run_eval.py` 头部有 `sys.path` 注入才能 import `app`）。
- 用例：主基准 `eval/eval_cases.jsonl` = **比赛给定 6 条，锁定不针对它过拟合**；内部扩展集 `eval/dev_cases.jsonl`（8 条，覆盖 6 条未涉及的场景：物流单号/价格/使用不当/竞品对比/平台投诉/严重症状/退换货/复购）用于压测泛化。两集字段均复用 `TriageAnalysis` 真实枚举 + `reply_rubric{must_contain,must_not,brand_compliance}`。
- 运行器 `eval/run_eval.py`：**直接 `graph.invoke(_make_state(req))` 拿完整 final state**（含 triage 原始 `risk` 全字段；`run_copilot` 的 CopilotResult 只暴露 risk_level，评安全维度不够），再用 `cost.session_totals(session_id)` 取成本。四维度：意图/情绪精确匹配 + **实体包含匹配 F1**（细粒度命中粗粒度也算中，但 precision/recall 双看，乱抽仍扣分）+ 风险布尔+severity序数 + 回复合规规则 + 成本。LLM-Judge 走 `--judge` 可选开关。每条 case 用自身 id 当 session_id 隔离成本。
- 用法：`uv run python eval/run_eval.py [--cases 关键词] [--limit N] [--judge]`（主基准→`eval/report.md`）；扩展集 `uv run python eval/run_eval.py --in-file eval/dev_cases.jsonl --out eval/report_dev.md`。
- **实体抽取已优化**（基线 F1 0.444→0.833）：`app/prompt/triage.py` 实体指令拓宽为商品/品类词+肌肤类型+订单/物流号，并排除症状词/金额/时间/订单状态；`app/agent/nodes/triage.py` 把 `state["orders"]` 拼成订单上下文喂给 triage（真实客服本就该知道顾客买了什么，仍为 1 次调用）。残留 EVAL-003 实体 0 是金标准粒度问题（要泛指"产品"，模型抽订单里的"精华"更准），属标注粒度，未改比赛标签。
- **评测集价值=同时测标注质量**：EVAL-003 曾连错三次金标准（primary 退款→订单服务、secondary 退款→赔偿、实体产品→精华）；DEV-003/DEV-005 也修过金标准。今后写 expected 应先跑一次 actual 再定标。
- **ruff**：`eval/run_eval.py` 需保持 `uv run ruff check .` 通过（已修 E402/B904/I001/F401/E731）；路径注入后的 import 用 `# noqa: E402`。

## 买家消息处理系统（六任务）最终落点
- 后端：`/api/chat/stream/{id}`（指令分支 + 原 chat 流 + 广播登记）、`POST /api/test/buyer_message`、`/health`。
- 前端：草稿面板"重新生成/调整语气"按钮经 WS 发 `optimize_expression`/`adjust_tone`，回写真实草稿。
- 测试：`tests/test_realtime.py`（指向 `/api/chat/stream/`）。

## 服务承诺跟踪闭环（2026-10-18 补齐，初赛标志性能力之一）
- 路由已全部挂载：`app/api/routes/promises.py`（GET 列表 / POST extract / POST scan / PATCH 状态）、`actions.py`（POST preview|confirm，幂等 `idempotency_key`）、`demo.py`（POST /api/demo/reset）、`risk.py`（GET /api/risk-queue）。`tickets.py` 有 POST 建单。
- **承诺抽取唯一触发点 = `session_service.append_message`**：仅 `role=="agent" and send=True`（最终发送）才调 `promise_service.create_promise_from_message`，草稿 send=False 不进入（PR-02）。返回体含 `promise` 字段。
- **WS 真实数据贯通**：`app/main.py` WS handler 用 `run.build_context_from_session(db, session_id, text)` + `_make_state` 按 session_id 从 DB 载入真实 messages/orders/tickets/events（替掉写死的 ORD-DEMO）；流结束把 reply_draft 作为 agent 消息落库（自动触发抽取）并广播 `analysis`+`promise`。
- 前端：`services/promise.ts`（`/api/promises`、`/api/promises/scan`，API_BASE=localhost:8000）；`RadarView.tsx` 拉真实数据、指标由数据算。
- 测试：`tests/test_promise_pipeline.py`（8 条，含抽取/草稿不抽/扫描/状态流转/建单/动作幂等/demo reset）。

### 踩坑（补齐时修的真 bug，勿再引入）
- `risk_service.py` 原引 `from app.agents import rules`：`app.agents` 拼写错且 `rules` 模块不存在→**整个 app 导入失败**（挂 risk 路由才暴露）。已改无依赖 `_fallback_reasons`。
- `ticket_service.create_ticket`：①漏 import `ServiceSession`；②`ServiceEvent.ticket_id` 误用 `ticket_no`（FK 失败，应用 `ticket_id`）；③`ServiceTicket.ticket_id` 无默认值，需显式 `f"T-{uuid4().hex[:12].upper()}"`；④`db.add(ticket)` 与 `db.add(event)` 间必须 `db.flush()`，否则子事件外键因插入顺序失败。
- `ActionConfirmRequest`（schemas/api.py）必须有顶层 `action_type`（preview 才有会漏），否则 confirm 时 AttributeError。`action_id` 可空。
- `app/agent/time.py`：`明天上午10点` 曾被 `_TOMORROW_RE` 只匹配时段、丢弃钟点→算成 12:00。已加 `_CLOCK_RE` 同时解析钟点（支持后天、下午/晚上+12 换算）。改后"明天上午10点"→次日 10:00。
- WS `analysis` 帧发送前必须 `jsonable_encoder`：`evidence` 含 `EvidenceRef`（pydantic 对象），直接 `websocket.send_json` 会崩。
- `/tmp` 在 Git Bash→C:\tmp，curl `--data-binary @/tmp/x` 读不到；测试 body 文件放项目目录用相对路径。

## 反「千人一面」个性化（模型/提示词层）
- 本机 gateway 可用（fast/reasoning is_available=True），**demo/eval 跑真实模型**；只有 mode="mock"（CI/无 key）走 mock。改个性化要同时看真实 prompt 和 mock。
- `REPLY_PROMPT`（app/prompt/reply.py）含 `{user_profile}` 变量，并把"先共情复述肤质/困扰 + 结合肤质给成分/用法专业建议 + 严禁只说爆款 + 不诊断/不荐药/不保证"列为硬性要求。HIGH_RISK 那套保持安全优先、勿加个性化放开。
- `mock.skin_profile(message, entities)`：肤质类型 + 困扰词表 → 画像串；`mock_reply(risk, evidence, message="", entities=None)` L0 分支据此个性化，无信息则主动追问肤质/困扰。`reply.py` 节点统一算 user_profile 并透传 message/entities。
- 测试：`tests/test_personalization.py`（skin_profile / 敏感肌个性化含"成分""建议"且无"爆款"/无红线词 / L3 不变 / prompt 必须含 user_profile·个性化·爆款·复述）。

## 商品库与售前推荐（2026-10-18 补）
- 数据库原有**无产品表**，售前只能引用用户历史订单 → 无商品可推。已加 `Product` 表 + `PRODUCT_CATALOG`（10 个在售 SKU：洁面/精华/面霜/面膜/防晒/乳液，各标 核心成分/适用肤质/功效/注意事项/价格）。`scripts/init_db.py` 建表、`apply_baseline`/reset 灌库（幂等 merge），`GET /api/products` 暴露。
- 检索链：`CopilotRequest.products` → `_make_state`(必带 products，曾漏加致产品从不进 state) → `tool_query` 仅 `售前咨询+L0` 调 `tools/product.match_products(entities, skin_type, products)` → `evidence` 出 `source_type=product` 证据（quote 含名称/成分/肤质/功效/注意事项）→ reply prompt 据此推荐真实商品。**已知肤质时只在适合肤质的商品里挑**（敏感肌不会拿到水杨酸）；高危/不良反应不匹配商品（不推销）。
- `run.load_product_context(db)` 供 WS `build_context_from_session` 与 `/api/test/buyer_message` 共用载入在售目录。
- 坑：售前 rubric `must_not` 含"保证"，prompt/回复勿出现"保证"字样（用"效果因人而异/供您参考"）；mock 模式 `mock_intent` 不抽品类实体且症状词误判不良反应，故 mock 下售前品类匹配弱，真实模型正常。
- 测试：`tests/test_product_recommendation.py`（肤质过滤/品类匹配/证据接入/高危不推/`/api/products`）。
