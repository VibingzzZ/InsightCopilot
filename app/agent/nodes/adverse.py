from app.agent.state import CustomerState


def adverse_node(state: CustomerState) -> CustomerState:
    state["reply_draft"] = "检测到较高风险，请进入不良反应处置流程。"
    return state
