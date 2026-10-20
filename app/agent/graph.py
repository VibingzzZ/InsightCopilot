from langgraph.graph import END, START, StateGraph

from app.agent.nodes.adverse import adverse_node
from app.agent.nodes.context import context_node
from app.agent.nodes.evidence import evidence_node
from app.agent.nodes.fact_check import fact_check_node
from app.agent.nodes.reply import reply_node
from app.agent.nodes.risk_engine import risk_engine_node
from app.agent.nodes.summary import summary_node
from app.agent.nodes.tool_query import tool_query_node
from app.agent.nodes.triage import triage_node
from app.agent.nodes.vision import vision_node
from app.agent.state import CustomerState


def route_by_risk(state: CustomerState) -> str:
    """L1 以上进不良反应专项，L0 走普通接待。"""
    return "adverse" if state["risk_level"] in {"L1", "L2", "L3"} else "normal"


builder = StateGraph(CustomerState)

builder.add_node("context", context_node)
# 降本：intent + emotion + risk_extraction 三次调用合并为一次（triage）
builder.add_node("triage", triage_node)
builder.add_node("risk_engine", risk_engine_node)
builder.add_node("tool_query", tool_query_node)
builder.add_node("evidence", evidence_node)
builder.add_node("summary", summary_node)
builder.add_node("vision", vision_node)
builder.add_node("adverse", adverse_node)
builder.add_node("reply", reply_node)
builder.add_node("fact_check", fact_check_node)

builder.add_edge(START, "context")
builder.add_edge("context", "triage")
builder.add_edge("triage", "risk_engine")
# 事实与证据在分支之前完成，保证两条路都拿得到证据
builder.add_edge("risk_engine", "tool_query")
builder.add_edge("tool_query", "evidence")
# 轨迹摘要在分支前完成，普通与高风险两条路都能拿到历史轨迹
builder.add_edge("evidence", "summary")
builder.add_conditional_edges(
    "summary",
    route_by_risk,
    {"adverse": "vision", "normal": "reply"},
)
# 高风险分支：先识别图片，再走不良反应专项处置
builder.add_edge("vision", "adverse")
builder.add_edge("adverse", "reply")
builder.add_edge("reply", "fact_check")
builder.add_edge("fact_check", END)

graph = builder.compile()
