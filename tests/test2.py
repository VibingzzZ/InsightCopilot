# 期望：adverse_reaction=True, medical_visit=True, risk_level="high"
from app.agent.nodes.risk_engine import risk_engine_node
from app.agent.nodes.risk_extraction import risk_extraction_node

state = {
    "conversation_id": "S",
    "current_message": "用了面霜之后脸红，而且去了医院",
    "intent": "",
    "emotion": "",
    "risk": {},
    "risk_level": "",
    "order": {},
    "evidence": [],
    "reply_draft": "",
}
state.update(risk_extraction_node(state))
print(state["risk"])  # {'adverse_reaction': True, 'symptoms': ['脸红'], 'medical_visit': True}
state.update(risk_engine_node(state))
print(state["risk_level"])  # high
