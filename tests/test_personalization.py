"""个性化 / 反「千人一面」回归测试。

对应产品诉求：顾客反复强调肤质困扰时，回复必须结合其肤质给出个性化、专业建议，
而不是千篇一律的爆款式通用回复；同时守住「不诊断 / 不荐药 / 不保证」红线。
"""

from app.agent.mock import mock_reply, skin_profile

# 与 test_agent.py 保持一致的红线词
FORBIDDEN = ("确诊", "病因", "口服", "服用", "抹药", "开药", "抗生素", "药物")


def test_skin_profile_extracts_type_and_concerns():
    assert skin_profile("我是敏感肌，脸经常泛红干燥") == "肤质：敏感肌；主要困扰：泛红、干燥"
    assert skin_profile("大油皮还总长痘") == "肤质：油性肌肤；主要困扰：长痘"
    assert skin_profile("今天天气不错") == ""
    # 消息没提肤质时，可从实体兜底
    assert skin_profile("能用这款吗", entities=["洁面", "敏感肌"]) == "肤质：敏感肌"


def test_mock_reply_personalizes_sensitive_skin():
    reply = mock_reply(
        "L0",
        ["订单状态：已签收；商品：氨基酸洁面 120g"],
        message="我是敏感肌，能用你们家氨基酸洁面吗？会不会致痘？",
        entities=["洁面", "敏感肌"],
    ).reply
    # 个性化：复述肤质 + 专业建议 + 含关键锚点词
    assert "敏感肌" in reply
    assert "成分" in reply
    assert "建议" in reply
    # 反千人一面：不应出现无差别爆款话术
    assert "爆款" not in reply
    # 红线
    for word in FORBIDDEN:
        assert word not in reply


def test_mock_reply_asks_when_no_skin_info():
    reply = mock_reply("L0", [], message="今天天气不错").reply
    # 无肤质信息时主动询问，而非通用「请问还需要什么」
    assert "肤质" in reply and "困扰" in reply


def test_mock_reply_high_risk_unchanged_and_safe():
    reply = mock_reply("L3", ["订单状态：已签收"]).reply
    assert "停止使用" in reply and "就医" in reply
    for word in FORBIDDEN:
        assert word not in reply


def test_reply_prompt_requires_personalization():
    """真实 prompt 必须把个性化写成硬性要求，并暴露 user_profile 变量。"""
    from app.prompt.reply import REPLY_PROMPT

    assert "{user_profile}" in REPLY_PROMPT
    assert "个性化" in REPLY_PROMPT
    # 反爆款 + 复述困扰 的引导必须在 prompt 里
    assert "爆款" in REPLY_PROMPT
    assert "复述" in REPLY_PROMPT
