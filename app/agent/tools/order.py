MOCK_ORDERS = {
    "0001": {
        "order_id": "0001",
        "status": "退款处理中",
        "product": "某护肤产品",
        "logistics": "暂无物流信息",
    },
    "0002": {
        "order_id": "0002",
        "status": "已发货",
        "product": "某面霜",
        "logistics": "运输中，预计 2 天后送达",
    },
}


def query_order(order_id: str) -> dict:
    """查询订单。V1 用 mock 数据，后续接真实数据库/接口。"""
    return MOCK_ORDERS.get(order_id, {})