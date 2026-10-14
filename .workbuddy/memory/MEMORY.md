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

## 买家消息处理系统（六任务）最终落点
- 后端：`/api/chat/stream/{id}`（指令分支 + 原 chat 流 + 广播登记）、`POST /api/test/buyer_message`、`/health`。
- 前端：草稿面板"重新生成/调整语气"按钮经 WS 发 `optimize_expression`/`adjust_tone`，回写真实草稿。
- 测试：`tests/test_realtime.py`（指向 `/api/chat/stream/`）。
