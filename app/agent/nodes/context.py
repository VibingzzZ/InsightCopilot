"""会话上下文节点。

业务事实（订单/工单/历史消息/承诺）已由后端在 CopilotRequest 里预组装，
这里只负责决定模型路由，不做任何查询。
"""

from app.agent.state import CustomerState
from app.integrations.model.gateway import gateway


def context_node(state: CustomerState) -> dict:
    mode = state.get("mode", "auto")

    # model_route 是给前端看的「这次结论是谁产出的」，不是调用参数
    if mode == "mock" or not gateway.is_available("reasoning"):
        route = "mock"
    else:
        route = "reasoning"

    return {"model_route": route}
