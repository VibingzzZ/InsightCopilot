from app.agent.graph import graph
from app.agent.state import CustomerState

if __name__ == "__main__":
    state: CustomerState = {
        "conversation_id": "S00005",
        "current_message": "我上次已经问过了，为什么还没退款？",
        "intent": "",
        "risk_level": "",
        "order": {},
        "evidence": [],
        "emotion": "",
        "reply_draft": "",
    }

    result = graph.invoke(state)

    print(result)
