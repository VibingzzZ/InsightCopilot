# WebSocket 报错 `Object of type EvidenceRef is not JSON serializable` 排查与修复方案

## 一、结论（TL;DR）

报错不是 Agent 返回的「内容」有问题，而是**序列化边界**问题：

- `app/main.py` 的 WebSocket 循环把 LangGraph 节点的**原始状态**（`node_state`）直接 `send_json` 出去；
- 状态里 `evidence` 字段是 `list[EvidenceRef]`（Pydantic 模型实例，不是 dict）；
- FastAPI 的 `WebSocket.send_json` 内部用的是**裸 `json.dumps`，不会自动把 Pydantic 模型转成 dict**；
- 所以 `EvidenceRef` 实例碰到 `json.dumps` 就抛 `Object of type EvidenceRef is not JSON serializable`。

你的初步判断（DTO/VO 与 Agent 返回信息的序列化问题）方向正确，准确说是「Pydantic DTO 没在 WS 出口转成 dict」。

---

## 二、出错链路

```
main.py:92  g.astream(initial_state, stream_mode="updates")
   └─ 每个节点产出 node_state（LangGraph 把 evidence 用 add reducer 累加）
        ├─ evidence.py:69   return {"evidence": [EvidenceRef(...)]}   ← Pydantic 对象
        ├─ vision.py:104    return {"vision": {...}, "evidence": [EvidenceRef(...)]}
main.py:95  websocket.send_json({"data": node_state})
   └─ FastAPI WebSocket.send_json → json.dumps(node_state)
        └─ TypeError: Object of type EvidenceRef is not JSON serializable
```

关键文件：

| 文件 | 行号 | 作用 |
|------|------|------|
| `app/main.py` | 92-101 | WS 流式循环，直接透传 `node_state` |
| `app/agent/state.py` | 54 | `evidence: Annotated[list[EvidenceRef], add]` |
| `app/agent/nodes/evidence.py` | 69 | 返回 `list[EvidenceRef]`（未 dump） |
| `app/agent/nodes/vision.py` | 97-104 | 返回 `EvidenceRef`（未 dump） |
| `app/agent/schemas/contract.py` | 24-30 | `EvidenceRef(BaseModel)` 定义 |

---

## 三、为什么「只有」 EvidenceRef 触发

全图节点的返回值里，**只有** `evidence` / `vision` 两个节点把 Pydantic 模型对象直接写进状态，其余节点都是纯 dict / str / bool：

- `risk_extraction.py:28` → `result.model_dump()`（已转 dict）
- `vision.py:104` → `result.model_dump()`（vision 已转 dict，但 `evidence` 没转）
- `adverse.py:163` → `assessment.model_dump()`（已转 dict）
- `context / intent / emotion / risk_engine / tool_query / summary / reply / fact_check` → 全是 `str / list / dict / bool`

`promise.py:71` 里的 `EvidenceRef` 走的是 REST 接口（`extract_promise_candidate`），不经过这个 WebSocket，因此不报错。

> 补充：`adverse._build_ticket_draft` 里的 `follow_up_due_at` 由 `normalize_due` 产出，已经是 ISO8601 字符串（`time.py:141` 的 `due.isoformat()`），不是 datetime，所以 adverse 分支没有二次坑。

---

## 四、修复方案

### 方案 A（推荐）：在 WS 出口统一转成 JSON 可序列化对象

只改 `app/main.py` 的序列化边界，Agent 层 / 状态契约保持不变。

```python
# main.py 顶部新增导入
from fastapi.encoders import jsonable_encoder

# 循环内改一处
async for event in g.astream(initial_state, stream_mode="updates"):
    for node_name, node_state in event.items():
        print(f"--- Node: {node_name} ---")
        await websocket.send_json(
            {
                "type": "node_update",
                "node": node_name,
                "data": jsonable_encoder(node_state),
            }
        )
        await asyncio.sleep(0.5)
```

**为什么这样改**：`jsonable_encoder` 会递归把 Pydantic 模型 → dict、datetime → ISO 字符串、set/tuple → list，正好覆盖 `EvidenceRef` 以及未来任何可能进状态的 Pydantic 对象。改动最小、最稳。

**优点**：
- 一处修改，覆盖当前和未来所有非 JSON 原生类型；
- 保持 `CustomerState.evidence` 仍是 `list[EvidenceRef]`，`reply_node` 里 `item.quote` 等下游消费不受影响；
- 不破坏「Agent 层对外 I/O 契约」的类型设计。

**缺点**：每个 node_update 都做一次全量递归编码，demo 数据量下开销可忽略。

---

### 方案 B（不推荐）：在节点源头 dump 成 dict

把 `evidence.py` / `vision.py` 的返回改成：

```python
return {"evidence": [e.model_dump() for e in items]}
return {"vision": result.model_dump(), "evidence": [evidence.model_dump()], "degraded": degraded}
```

**不推荐的原因**：
- 状态里 `evidence` 的类型语义会从 `EvidenceRef` 变成 dict，与 `state.py:54` 的 `Annotated[list[EvidenceRef], add]` 声明不一致；
- 将来新增节点若再忘了 `model_dump`，又会复发；治标不治本；
- 边界职责错位：序列化是「出口」的职责，不该压给每个 Agent 节点。

---

### 方案 C（备选，若想彻底规避裸 json.dumps）：给 WS 写一个安全的 send 封装

如果以后还有其它 WebSocket 出口要发 LangGraph 状态，可以抽一个 helper：

```python
async def _send_json_safe(ws: WebSocket, payload: dict) -> None:
    await ws.send_json(jsonable_encoder(payload))
```

并把所有 `send_json` 调用统一收敛到这里。适合 WebSocket 出口会变多的场景。

---

## 五、验证方法

1. 启动后端：`python app/main.py`（或 `uvicorn app.main:app`），前端连上 `ws://localhost:8000/api/chat/stream/{session_id}`；
2. 发送任意一条消息，观察后端控制台：
   - 修复前：打印到 `--- Node: evidence ---` 后立刻抛 `[WebSocket] Error: Object of type EvidenceRef is not JSON serializable`，前端收不到 `done`；
   - 修复后：能依次打印 context → intent → … → reply → fact_check，前端正常收到 `node_update`，`reply` 节点的 `reply_draft` 被追加进聊天流，最后收到 `{"type": "done"}`。
3. 若需覆盖高风险分支，可发送含「过敏 / 红肿 / 呼吸困难」等词的消息，确认 `vision` / `adverse` 分支也不报序列化错。

---

## 六、附：FastAPI WebSocket.send_json 的真实实现（已验证）

环境：`fastapi 0.141.1 / starlette 1.6.0`。

```python
# fastapi/websockets.py（0.141.1）
async def send_json(self, data: Any, mode: str = "text") -> None:
    if mode not in {"text", "binary"}:
        raise RuntimeError('The "mode" argument should be "text" or "binary".')
    text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if mode == "text":
        await self.send({"type": "websocket.send", "text": text})
    else:
        await self.send({"type": "websocket.send", "bytes": text.encode("utf-8")})
```

注意：这里**没有** `jsonable_encoder`（区别于 FastAPI 的 REST `JSONResponse`），所以 Pydantic 模型会直接崩。这就是根因的直接证据。
