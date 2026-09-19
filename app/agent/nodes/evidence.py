from app.agent.state import CustomerState


def evidence_node(state: CustomerState) -> CustomerState:
    order = state["order"]

    state["evidence"].append({
        "source": "order",
        "id": order["order_id"],
        "content": f"订单状态：{order['status']}"
    })

    return state