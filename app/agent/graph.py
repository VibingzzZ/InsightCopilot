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
builder.add_edge("adverse", "reply")   # ← 关键：high 分支也汇入 reply
builder.add_edge("reply", END)

graph = builder.compile()