from langgraph.graph import END, START, StateGraph

from app.agent.nodes.adverse import adverse_node
from app.agent.nodes.context import context_node
from app.agent.nodes.emotion import emotion_node
from app.agent.nodes.evidence import evidence_node
from app.agent.nodes.fact_check import fact_check_node
from app.agent.nodes.intent import intent_node
from app.agent.nodes.reply import reply_node
from app.agent.nodes.risk_engine import risk_engine_node
from app.agent.nodes.risk_extraction import risk_extraction_node
from app.agent.nodes.tool_query import tool_query_node
from app.agent.state import CustomerState


def route_by_risk(state: CustomerState) -> str:
    """L1 以上进不良反应专项，L0 走普通接待。"""
    return "adverse" if state["risk_level"] in {"L1", "L2", "L3"} else "normal"


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
builder.add_node("fact_check", fact_check_node)

builder.add_edge(START, "context")
builder.add_edge("context", "intent")
builder.add_edge("intent", "emotion")
builder.add_edge("emotion", "risk_extraction")
builder.add_edge("risk_extraction", "risk_engine")
# 事实与证据在分支之前完成，保证两条路都拿得到证据
builder.add_edge("risk_engine", "tool_query")
builder.add_edge("tool_query", "evidence")
builder.add_conditional_edges(
    "evidence",
    route_by_risk,
    {"adverse": "adverse", "normal": "reply"},
)
builder.add_edge("adverse", "reply")
builder.add_edge("reply", "fact_check")
builder.add_edge("fact_check", END)

graph = builder.compile()
