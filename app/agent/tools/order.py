def query_order(order_id: str) -> dict:
    mock_orders = {
        "0001": {
            "order_id": "0001",
            "status": "退款处理中",
            "product": "某护肤产品",
        }
    }

    return mock_orders.get(order_id, {})
