"""证据汇总节点。

把订单/工单事实压成统一的 EvidenceRef 结构。Reply 只信这一层，
不直接读原始业务字段，这样以后新增证据来源（物流、规则、承诺）时 Reply 不用改。
"""

from app.agent.schemas.contract import EvidenceRef
from app.agent.state import CustomerState
from app.agent.tools.order import (
    order_id_of,
    order_status_of,
    product_name_of,
    tracking_of,
)
from app.agent.tools.ticket import ticket_id_of, ticket_status_of, ticket_type_of


def _order_evidence(order: dict) -> EvidenceRef | None:
    order_id = order_id_of(order)
    if not order_id:
        return None

    parts = []
    if order_status_of(order):
        parts.append(f"订单状态：{order_status_of(order)}")
    if product_name_of(order):
        parts.append(f"商品：{product_name_of(order)}")
    if tracking_of(order):
        parts.append(f"物流：{tracking_of(order)}")

    return EvidenceRef(
        source_type="order",
        source_id=order_id,
        quote="；".join(parts) if parts else "订单已关联",
    )


def _ticket_evidence(ticket: dict) -> EvidenceRef | None:
    ticket_id = ticket_id_of(ticket)
    if not ticket_id:
        return None

    parts = []
    if ticket_type_of(ticket):
        parts.append(f"工单类型：{ticket_type_of(ticket)}")
    if ticket_status_of(ticket):
        parts.append(f"工单状态：{ticket_status_of(ticket)}")

    return EvidenceRef(
        source_type="ticket",
        source_id=ticket_id,
        quote="；".join(parts) if parts else "存在关联工单",
    )


def evidence_node(state: CustomerState) -> dict:
    items: list[EvidenceRef] = []

    order_item = _order_evidence(state.get("linked_order") or {})
    if order_item:
        items.append(order_item)

    for ticket in state.get("linked_tickets") or []:
        ticket_item = _ticket_evidence(ticket)
        if ticket_item:
            items.append(ticket_item)

    # evidence 字段是 add reducer，这里只返回新增条目，框架自动累加
    return {"evidence": items}
