"""端到端验证：通过 8000 的 WS 跑一次真实对话，捕获 cost_summary 帧。"""
import asyncio
import json
import sys

import websockets

URI = "ws://127.0.0.1:8000/api/chat/stream/TEST-E2E-001"
TEXT = "我的订单 ORD-DEMO 什么时候发货？还有赠品吗"


async def main():
    async with websockets.connect(URI) as ws:
        await ws.send(json.dumps({"text": TEXT}))
        cost_frame = None
        node_count = 0
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
            except asyncio.TimeoutError:
                print("TIMEOUT waiting for frames")
                break
            msg = json.loads(raw)
            t = msg.get("type")
            if t == "node_update":
                node_count += 1
                print(f"  node_update: {msg.get('node')}")
            elif t == "cost_summary":
                cost_frame = msg
                print("  cost_summary:", json.dumps(msg, ensure_ascii=False))
            elif t == "done":
                print("  done")
                break
            elif t == "error":
                print("  error:", json.dumps(msg, ensure_ascii=False))
                break
            else:
                print(f"  {t}: {json.dumps(msg, ensure_ascii=False)[:120]}")
        print("\n=== RESULT ===")
        print("node_updates:", node_count)
        if cost_frame:
            t = cost_frame["totals"]
            yuan = (t.get("cost_yuan") if isinstance(t.get("cost_yuan"), (int, float)) else (t.get("cost_cent") or 0) / 100)
            degraded_pct = round((t.get("degraded", 0) / t["calls"]) * 100) if t.get("calls") else 0
            print(f"  calls={t.get('calls')} tokens={t.get('total_tokens')} cost_yuan={yuan} degraded%={degraded_pct}")
            print(f"  >>> 前端将提示: 本次 AI 消耗 ¥{yuan:.4f}（{t.get('calls')} 次调用 / 共 {t.get('total_tokens')} tokens，降级 {degraded_pct}%）")
        else:
            print("  !! 未收到 cost_summary 帧")


asyncio.run(main())
