from app.agent.state import CustomerState
from app.agent.tools.order import query_order


def tool_query_node(state: CustomerState) -> dict:
    # 根据 intent 路由到具体工具；V1 只接了订单工具。
    # 未来：物流 → query_logistics，工单 → query_ticket。
    intent = state["intent"]

    # intent 是 LLM 自由文本，不能精确匹配；用关键词判断更稳
    if any(kw in intent for kw in ("退款", "物流", "订单")):
        order = query_order("0001")   # TODO: 换成从会话/数据库关联真实订单号
        return {"order": order}

    return {"order": {}}