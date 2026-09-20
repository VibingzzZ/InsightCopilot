from langgraph.graph import END, START, StateGraph

from app.agent.nodes.adverse import adverse_node
from app.agent.nodes.context import context_node
from app.agent.nodes.emotion import emotion_node
from app.agent.nodes.evidence import evidence_node
from app.agent.nodes.intent import intent_node
from app.agent.nodes.reply import reply_node
from app.agent.nodes.risk import risk_node
from app.agent.state import CustomerState


def route_by_risk(state: CustomerState) -> str:
    if state["risk_level"] == "high":
        return "adverse"
    return "normal"


# 创建一个以CustomerState为状态结构的流程图
builder = StateGraph(CustomerState)

# 增加节点
builder.add_node("adverse", adverse_node)
builder.add_node("context", context_node)
builder.add_node("intent", intent_node)
builder.add_node("emotion", emotion_node)
builder.add_node("risk", risk_node)
builder.add_node("evidence", evidence_node)
builder.add_node("reply", reply_node)


builder.add_edge(START, "context")
builder.add_edge("context", "intent")
builder.add_edge("intent", "emotion")
builder.add_edge("emotion", "risk")
builder.add_conditional_edges(
    "risk",
    route_by_risk,
    {
        "normal": "evidence",
        "adverse": "adverse",
    },
)

builder.add_edge("evidence", "reply")
builder.add_edge("reply", END)
builder.add_edge("adverse", END)


graph = builder.compile()
