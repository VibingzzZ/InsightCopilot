"""商品检索（确定性规则，不调用模型）。

售前咨询时，从商品库中按「品类实体 + 肤质适配」挑出可推荐的在售商品，
作为 EvidenceRef 喂给 Reply。原则：
- 只在售（on_shelf）商品进入候选；
- 已知肤质时，优先只在适合该肤质的商品里挑，避免给敏感肌推水杨酸等刺激品；
- 品类由实体命中（面霜/精华/洁面/面膜/防晒/乳液），无品类命中时按肤质适配推荐；
- 一个都不匹配就返回空，绝不编造商品。
"""

from typing import Any

# 品类词：用于从实体里识别用户想买的品类
CATEGORY_WORDS = ("洁面", "精华", "面霜", "面膜", "防晒", "乳液", "水乳", "爽肤水", "眼霜")


def _on_shelf(product: dict[str, Any]) -> bool:
    return str(product.get("status") or "on_shelf") == "on_shelf"


def _skins(product: dict[str, Any]) -> list[str]:
    raw = product.get("suitable_skin_types")
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    return [part.strip() for part in str(raw or "").replace("，", ",").split(",") if part.strip()]


def _category_hits(entities: list[str]) -> set[str]:
    hits: set[str] = set()
    for entity in entities:
        text = str(entity or "")
        for word in CATEGORY_WORDS:
            if word in text:
                hits.add(word)
    return hits


def match_products(
    entities: list[str],
    skin_type: str | None,
    products: list[dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """返回按相关度排序的在售商品（最多 limit 个）。"""
    available = [p for p in (products or []) if _on_shelf(p)]
    if not available:
        return []

    cat_hits = _category_hits(entities or [])

    # 肤质适配优先：已知肤质时，只在适合该肤质的商品里挑（有适合的才收窄）
    pool = available
    if skin_type:
        suited = [p for p in available if skin_type in _skins(p)]
        if suited:
            pool = suited

    scored: list[tuple[int, dict[str, Any]]] = []
    for product in pool:
        score = 0
        if product.get("category") in cat_hits:
            score += 2
        if skin_type and skin_type in _skins(product):
            score += 1
        if score > 0:
            scored.append((score, product))

    # 品类命中优先，其次按名称稳定排序，保证结果可复现
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    return [product for _, product in scored[:limit]]
