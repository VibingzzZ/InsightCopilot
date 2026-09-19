from app.agent.state import CustomerState
from app.agent.tools.order import query_order


def context_node(state: CustomerState) -> CustomerState:
    order = query_order("0001")

    state["order"] = order

    return state