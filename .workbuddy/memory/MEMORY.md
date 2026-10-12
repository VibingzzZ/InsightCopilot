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

## 工作流坑
- 本机可能有**上一轮遗留的 uvicorn 进程占用 8011**（沙箱无法 kill）。新起验证服务请用别的端口（如 8021），避免打到旧代码。
- 改造性未提交改动易被工作树重置吃掉；对已有文件的编辑要连同新文件一起提交。

## 买家消息处理系统（六任务）最终落点
- 后端：`/api/chat/stream/{id}`（指令分支 + 原 chat 流 + 广播登记）、`POST /api/test/buyer_message`、`/health`。
- 前端：草稿面板"重新生成/调整语气"按钮经 WS 发 `optimize_expression`/`adjust_tone`，回写真实草稿。
- 测试：`tests/test_realtime.py`（指向 `/api/chat/stream/`）。
