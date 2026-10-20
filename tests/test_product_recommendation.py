"""售前商品推荐回归测试。

对应诉求：系统内置公司产品库后，售前咨询能基于真实在售商品、结合顾客肤质
给出可推荐的匹配商品（作为证据），而不是「没有产品信息」或千人一面推爆款。
"""

from app.agent.graph import graph
from app.agent.run import _make_state
from app.agent.schemas.contract import CopilotRequest
from app.agent.tools.product import match_products
from app.db.baseline_data import PRODUCT_CATALOG


def _catalog() -> list[dict]:
    return [dict(p) for p in PRODUCT_CATALOG]


def _run(message: str):
    req = CopilotRequest(
        session_id="S-PROD",
        current_message=message,
        messages=[{"message_id": "M1", "sender_type": "customer", "message_text": message, "content_type": "text"}],
        orders=[],
        products=_catalog(),
        mode="mock",
    )
    return graph.invoke(_make_state(req))


def test_match_products_respects_skin_type():
    # 敏感肌 + 面霜：命中舒缓修护面霜，且绝不返回含刺激的水杨酸（仅油性）
    matched = match_products(["面霜", "敏感肌"], "敏感肌", _catalog())
    names = [p["name"] for p in matched]
    assert any("舒缓修护面霜" in n for n in names)
    assert all("水杨酸" not in n for n in names)


def test_match_products_by_category_when_no_skin():
    # 无肤质信息时按品类命中
    matched = match_products(["精华"], None, _catalog())
    assert matched
    assert all(p["category"] == "精华" for p in matched)


def test_match_products_empty_when_nothing_relevant():
    assert match_products([], None, []) == []


def test_presale_matches_products_as_evidence():
    final = _run("我是敏感肌，想买一款温和不刺激的面霜，有推荐吗")
    assert final["intent"]["primary"] == "售前咨询"
    assert final["risk_level"] == "L0"
    matched = final.get("matched_products") or []
    assert matched, "售前咨询应匹配到在售商品"
    # 证据层出现 product 类型
    product_ev = [e for e in final.get("evidence") or [] if e.source_type == "product"]
    assert product_ev
    # 推荐都与敏感肌适配（不含仅油性可用的刺激品）
    assert all("水杨酸" not in (e.quote or "") for e in product_ev)


def test_adverse_does_not_recommend_products():
    """高风险/不良反应场景不推荐商品，避免在用户不适时推销。"""
    final = _run("用了你们家精华全脸红肿还起疹子，痒得睡不着")
    assert final["risk_level"] in {"L1", "L2", "L3"}
    assert (final.get("matched_products") or []) == []
    assert not any(e.source_type == "product" for e in (final.get("evidence") or []))


def test_products_endpoint_lists_catalog(seeded_client):
    resp = seeded_client.get("/api/products")
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) >= 8
    sample = items[0]
    for key in ("product_id", "name", "category", "suitable_skin_types", "price_display"):
        assert key in sample
