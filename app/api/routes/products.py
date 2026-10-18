# 商品库路由：公司产品信息（售前推荐的事实来源）

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.deps import get_db
from app.core.envelope import ok
from app.models import Product
from app.services import serializers

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
def list_products(
    request: Request,
    db: Annotated[DbSession, Depends(get_db)],
    category: str | None = Query(None, description="按品类筛选：洁面/精华/面霜/面膜/防晒/乳液"),
    status: str = Query("on_shelf", description="默认只返回在售商品"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    if status:
        query = query.where(Product.status == status)
    rows = db.execute(query.order_by(Product.category.asc(), Product.name.asc()).limit(limit)).scalars().all()
    items = [serializers.product_item(p) for p in rows]
    return ok(request, {"items": items, "total": len(items)})
