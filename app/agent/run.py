from app.agent.graph import graph
from app.agent.state import CustomerState


def make_state(message: str) -> CustomerState:
    return {
        "conversation_id": "S00005",
        "current_message": message,
        "intent": "",
        "emotion": "",
        "risk": {"adverse_reaction": False, "symptoms": [], "medical_visit": False},
        "risk_level": "",
        "order": {},
        "evidence": [],
        "reply_draft": "",
    }


CASES = {
    "退款": "我上次已经问过了，为什么还没退款？",
    "不良反应": "用了这个面霜以后脸特别红，而且很疼，我已经去医院了。",
    "物流": "我的快递怎么还没到？",
}


if __name__ == "__main__":
    for name, message in CASES.items():
        print(f"\n===== Case: {name} =====")
        result = graph.invoke(make_state(message))
        print("intent     :", result["intent"])
        print("emotion    :", result["emotion"])
        print("risk       :", result["risk"])
        print("risk_level :", result["risk_level"])
        print("evidence   :", result["evidence"])
        print("reply      :", result["reply_draft"])
