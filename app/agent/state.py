from typing import TypedDict


# 实现Node间共享数据
class CustomerState(TypedDict):
    # 上下文及对话ID
    conversation_id: str
    current_message: str

    # 风险等级和目的
    intent: str
    risk_level: str

    # 订单及相关证明
    order: dict[str, str]
    evidence: list[dict[str, str]]

    # 回复草稿
    reply_draft: str

    # 用户情绪
    emotion: str
