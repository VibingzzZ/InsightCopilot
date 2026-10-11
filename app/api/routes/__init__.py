# 路由聚合：main.py 以 /api 前缀统一挂载
#
# 当前开发阶段仅挂载核心数据查询与管理接口：
#   会话/消息（sessions）、客户（customers）、订单（orders）、工单（tickets）、健康检查（health）。
# 已下线（代码保留，未挂载）：
#   风险队列 app/api/routes/risk.py；Agent 副驾与 SSE app/api/routes/deprecated_agent.py。
# 恢复方式：在下方重新 include_router 对应 router 即可。

from fastapi import APIRouter

from app.api.routes import customers, health, orders, sessions, tickets

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(customers.router)
api_router.include_router(orders.router)
api_router.include_router(tickets.router)
