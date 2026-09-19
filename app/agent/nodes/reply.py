from app.agent.state import CustomerState


def reply_node(state: CustomerState) -> CustomerState:
    order = state["order"]

    state["reply_draft"] = (
        f"您好，查询到您的订单 {order['order_id']} 目前状态为「{order['status']}」，请您耐心等待。"
    )

    return state
