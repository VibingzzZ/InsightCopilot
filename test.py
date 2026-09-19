from app.agent.nodes.context import context_node
from app.agent.nodes.evidence import evidence_node
from app.agent.nodes.intent import intent_node
from app.agent.nodes.reply import reply_node
from app.agent.nodes.risk import risk_node
from app.agent.state import CustomerState

state: CustomerState = {
    "conversation_id": "S00005",
    "current_message": "我上次已经问过了，为什么还没退款？",
    "intent": "",
    "risk_level": "",
    "order": {},
    "evidence": [],
    "reply_draft": "",
}
state = intent_node(state)
state = risk_node(state)
state = context_node(state)
state = evidence_node(state)
state = reply_node(state)

print(state)