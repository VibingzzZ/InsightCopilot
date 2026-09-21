from app.agent.state import CustomerState


def evidence_node(state: CustomerState) -> dict:
    order = state["order"]
    items = []

    if order:
        items.append(
            {
                "source": "order",
                "id": order["order_id"],
                "content": f"订单状态：{order['status']}",
            }
        )

    # 未来追加：
    # items.append({"source": "ticket", "id": "T001", "content": "客服工单处理中"})
    # items.append({"source": "logistics", "id": order["order_id"], "content": order["logistics"]})

    # 因为 evidence 字段用了 add reducer，这里返回新增条目即可，框架自动累加
    return {"evidence": items}
