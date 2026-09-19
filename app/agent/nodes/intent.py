from app.agent.state import CustomerState


def intent_node(state: CustomerState) -> CustomerState:
    message = state["current_message"]

    if "退款" in message:
        state["intent"] = "退款进度咨询"

    return state