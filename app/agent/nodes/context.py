from app.agent.state import CustomerState


def context_node(state: CustomerState) -> dict:
    # 加载会话上下文。
    # V1：先用 conversation_id 占位，不查任何业务数据。
    # TODO:后续从数据库按 conversation_id 拉取历史消息。
    return {}
