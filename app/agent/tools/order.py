"""订单事实字段访问器。

订单数据由后端在 CopilotRequest.orders 里查好传入，Agent 不查库。
后端字段名可能有差异，这里统一做「多候选 key + 回退」，避免因为改名炸掉链路。
"""

_ORDER_ID_KEYS = ("order_id", "order_no", "id")
_ORDER_STATUS_KEYS = ("order_status", "status")
_ORDER_PRODUCT_KEYS = ("product_name", "sku")
_ORDER_BATCH_KEYS = ("batch_no_masked", "batch_no")
_ORDER_TRACKING_KEYS = ("tracking_no_masked", "tracking_no")


def _pick(source: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = source.get(key)
        if value:
            return str(value)
    return ""


def order_id_of(order: dict) -> str:
    return _pick(order, _ORDER_ID_KEYS)


def order_status_of(order: dict) -> str:
    return _pick(order, _ORDER_STATUS_KEYS)


def product_name_of(order: dict) -> str:
    return _pick(order, _ORDER_PRODUCT_KEYS)


def batch_no_of(order: dict) -> str:
    return _pick(order, _ORDER_BATCH_KEYS)


def tracking_of(order: dict) -> str:
    return _pick(order, _ORDER_TRACKING_KEYS)
