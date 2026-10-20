# 路由聚合：main.py 以 /api 前缀统一挂载
#
# 已挂载：核心数据查询（sessions/customers/orders/tickets/products）、健康检查（health）、
# 成本（cost）、上传（uploads），以及初赛闭环所需的能力接口：
# 承诺跟踪（promises）、动作预览/确认（actions）、风险队列（risk-queue）、Demo 重置（demo）。
# 下线保留：Agent 副驾与 SSE app/api/routes/deprecated_agent.py（迁移至 WS 流）。

from fastapi import APIRouter

from app.api.routes import (
    actions,
    cost,
    customers,
    demo,
    health,
    orders,
    products,
    promises,
    risk,
    sessions,
    tickets,
    uploads,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(cost.router)
api_router.include_router(sessions.router)
api_router.include_router(customers.router)
api_router.include_router(orders.router)
api_router.include_router(tickets.router)
api_router.include_router(promises.router)
api_router.include_router(actions.router)
api_router.include_router(risk.router)
api_router.include_router(demo.router)
api_router.include_router(products.router)
api_router.include_router(uploads.router)
