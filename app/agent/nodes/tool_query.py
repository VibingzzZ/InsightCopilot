"""事实关联节点。

后端已在 CopilotRequest 里查好 orders / tickets，这里只做「关联」：
按意图识别出的实体（订单号等）把当前任务相关的订单和工单挑出来。

原则：
- 查不到就返回空，**绝不编造**订单号、状态或时间。
- 关联不确定（多条订单且没有实体命中）时返回空，交给客服选择，
  而不是随手挑一条，避免把 A 订单的事实说给 B 订单的消费者。
"""

from app.agent.state import CustomerState
from app.agent.tools.order import order_id_of, product_name_of, tracking_of
from app.agent.tools.ticket import ticket_id_of


def _match_order(orders: list[dict], entities: list[str]) -> dict:
    if not orders:
        return {}

    # 1. 实体直接命中订单号
    for order in orders:
        order_id = order_id_of(order)
        if order_id and order_id in entities:
            return order

    # 2. 实体命中商品名或物流号
    for entity in entities:
        if not entity:
            continue
        for order in orders:
            haystack = " ".join([order_id_of(order), product_name_of(order), tracking_of(order)])
            if entity in haystack:
                return order

    # 3. 只关联到一个订单时可以直接用；多个则不猜
    return orders[0] if len(orders) == 1 else {}


def _match_tickets(tickets: list[dict], linked_order: dict, session_id: str) -> list[dict]:
    matched: list[dict] = []
    order_id = order_id_of(linked_order)

    for ticket in tickets:
        ticket_order = str(ticket.get("order_id") or "")
        ticket_session = str(ticket.get("session_id") or "")

        if (order_id and ticket_order == order_id) or (session_id and ticket_session == session_id):
            matched.append(ticket)

    return matched


def tool_query_node(state: CustomerState) -> dict:
    entities = state.get("intent", {}).get("entities") or []
    orders = state.get("orders") or []
    tickets = state.get("tickets") or []

    linked_order = _match_order(orders, entities)
    linked_tickets = _match_tickets(tickets, linked_order, state.get("session_id", ""))

    # ticket_id_of 在这里只用于保证工单是可用结构，避免把空字典带进证据层
    linked_tickets = [t for t in linked_tickets if ticket_id_of(t)]

    return {"linked_order": linked_order, "linked_tickets": linked_tickets}
