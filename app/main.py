import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent.graph import graph

app = FastAPI(title="InsightCopilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HealthResponse(BaseModel):
    status: str

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")

@app.websocket("/api/chat/stream/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    print(f"[WebSocket] Connected: {session_id}")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            text = payload.get("text", "")
            
            print(f"[WebSocket] Received from {session_id}: {text}")
            
            # 构造 LangGraph 初始状态，使用 mock mode 防止没有配置 API key 时崩溃
            initial_state = {
                "session_id": session_id,
                "customer_name_masked": "消费者",
                "current_message": text,
                "messages": [{"role": "buyer", "text": text}],
                "orders": [{"id": "ORD-DEMO", "item": "测试商品"}],
                "tickets": [],
                "promises": [],
                "events": [],
                "mode": "mock" # 强制使用降级数据，以便能在没有后端凭证的电脑上跑通流程
            }
            
            await websocket.send_json({"type": "start"})
            
            # 迭代 LangGraph
            async for event in graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_state in event.items():
                    print(f"--- Node: {node_name} ---")
                    await websocket.send_json({
                        "type": "node_update",
                        "node": node_name,
                        "data": node_state
                    })
                    await asyncio.sleep(0.5)
            
            await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"[WebSocket] Disconnected: {session_id}")
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
