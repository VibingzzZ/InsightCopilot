from app.agent.state import CustomerState


def risk_node(state: CustomerState) -> CustomerState:
    if state["intent"] == "退款进度咨询":
        state["risk_level"] = "medium"

    return state