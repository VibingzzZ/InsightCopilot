"""工单事实字段访问器。

工单数据由后端在 CopilotRequest.tickets 里查好传入，Agent 不查库。
"""

_TICKET_ID_KEYS = ("ticket_id", "ticket_no", "id")
_TICKET_TYPE_KEYS = ("ticket_type",)
_TICKET_STATUS_KEYS = ("status", "ticket_status")
_TICKET_ASSIGNEE_KEYS = ("assignee", "owner")


def _pick(source: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = source.get(key)
        if value:
            return str(value)
    return ""


def ticket_id_of(ticket: dict) -> str:
    return _pick(ticket, _TICKET_ID_KEYS)


def ticket_type_of(ticket: dict) -> str:
    return _pick(ticket, _TICKET_TYPE_KEYS)


def ticket_status_of(ticket: dict) -> str:
    return _pick(ticket, _TICKET_STATUS_KEYS)


def ticket_assignee_of(ticket: dict) -> str:
    return _pick(ticket, _TICKET_ASSIGNEE_KEYS)
