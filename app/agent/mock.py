"""确定性 Mock 输出。

用途：
1. 没有 API Key 或断网时，整条链路仍能跑完并演示（文档质量门槛要求）。
2. 单测不依赖外部模型，断言可重复。

全部按关键词规则产出，不引入随机性。
"""

import re

from app.agent.schemas.analysis import (
    EmotionAnalysis,
    IntentAnalysis,
    PromiseExtraction,
    ReplyDraft,
    RewriteResult,
    RiskExtraction,
    TrajectorySummary,
    VisionExtraction,
)

# 不良反应症状词
SYMPTOM_WORDS = (
    "红肿",
    "泛红",
    "脸红",
    "刺痛",
    "疼痛",
    "很疼",
    "疼",
    "瘙痒",
    "发痒",
    "痒",
    "起疹",
    "疹子",
    "爆痘",
    "痘痘",
    "肿胀",
    "过敏",
    "脱皮",
    "灼热",
)
# 就医信号
MEDICAL_WORDS = ("医院", "就医", "医生", "挂号", "住院", "急诊", "门诊", "看过病", "挂了号")
# 监管投诉 / 舆情信号。普通"投诉"不算，避免过度触发 L3。
REGULATORY_WORDS = ("12315", "消协", "监管", "曝光", "起诉", "律师", "媒体", "工商")
# 不适程度词，顺序不能反：严重的必须先判
SEVERE_WORDS = ("呼吸困难", "喘不上气", "眼部", "眼睛肿", "住院", "晕倒", "昏迷")
OBVIOUS_WORDS = ("加重", "扩大", "越来越", "一直没好", "整个脸", "大面积", "好几天了", "更严重")
# 情绪信号
ANXIOUS_WORDS = ("着急", "急", "还没", "怎么还", "等很久", "催", "多久")
ANGRY_WORDS = ("太差", "差劲", "骗子", "无语", "垃圾", "投诉")
# 场景关键词
REFUND_WORDS = ("退款", "打款", "到账", "价保", "退钱")
LOGISTICS_WORDS = ("快递", "物流", "发货", "到货", "签收", "包裹", "运单")

# 肤质类型（命中最长/最具体的优先，故按顺序遍历取第一个）
SKIN_TYPE_WORDS: tuple[tuple[str, str], ...] = (
    ("混合皮", "混合性肌肤"),
    ("混合性", "混合性肌肤"),
    ("敏感肌", "敏感肌"),
    ("敏感性", "敏感肌"),
    ("干皮", "干性肌肤"),
    ("干性", "干性肌肤"),
    ("油皮", "油性肌肤"),
    ("油性", "油性肌肤"),
    ("中性", "中性肌肤"),
)
# 肤质困扰 / 关注点（用于个性化建议）
CONCERN_WORDS: tuple[tuple[str, str], ...] = (
    ("泛红", "泛红"),
    ("红血丝", "泛红"),
    ("干燥", "干燥"),
    ("起皮", "干燥起皮"),
    ("脱皮", "干燥起皮"),
    ("紧绷", "干燥紧绷"),
    ("爆痘", "爆痘"),
    ("长痘", "长痘"),
    ("痘痘", "长痘"),
    ("闭口", "闭口粉刺"),
    ("粉刺", "闭口粉刺"),
    ("毛孔", "毛孔粗大"),
    ("黑头", "黑头"),
    ("暗沉", "暗沉"),
    ("黄气", "暗沉"),
    ("提亮", "提亮肤色"),
    ("美白", "提亮肤色"),
    ("细纹", "细纹"),
    ("抗老", "抗老紧致"),
    ("抗皱", "抗老紧致"),
    ("紧致", "抗老紧致"),
    ("斑点", "色斑"),
    ("晒斑", "色斑"),
    ("过敏", "易过敏"),
    ("保湿", "保湿"),
    ("修护", "屏障修护"),
    ("屏障", "屏障修护"),
)

_ORDER_NO_RE = re.compile(r"\d{6,}")


# 否定词：紧邻关键词之前的否定会取消命中（「没有红肿」「不痒」不算不良反应）
_NEGATION_WORDS = ("没有", "没", "不是", "并非", "不", "无", "未", "否认", "排除")


def _is_negated(text: str, pos: int) -> bool:
    """判断 text 中 pos 处的关键词是否被其前面紧邻的否定词修饰。"""
    window = text[max(0, pos - 4) : pos]
    return any(neg in window for neg in _NEGATION_WORDS)


def _word_hit(text: str, word: str) -> bool:
    """关键词命中且至少有一处未被否定。"""
    return any(not _is_negated(text, m.start()) for m in re.finditer(re.escape(word), text))


def _hit(text: str, words: tuple[str, ...]) -> bool:
    return any(_word_hit(text, word) for word in words)


def _hits(text: str, words: tuple[str, ...]) -> list[str]:
    return [word for word in words if _word_hit(text, word)]


def mock_intent(message: str) -> IntentAnalysis:
    entities = _ORDER_NO_RE.findall(message)

    if _hit(message, SYMPTOM_WORDS) or _hit(message, MEDICAL_WORDS):
        return IntentAnalysis(
            intent_primary="不良反应",
            intent_secondary="过敏就医" if _hit(message, MEDICAL_WORDS) else "轻度不适",
            entities=entities,
        )

    if _hit(message, REFUND_WORDS):
        return IntentAnalysis(intent_primary="订单服务", intent_secondary="退款迟迟不到账", entities=entities)

    if _hit(message, LOGISTICS_WORDS):
        return IntentAnalysis(intent_primary="物流问题", intent_secondary="物流停滞未更新", entities=entities)

    return IntentAnalysis(intent_primary="售前咨询", intent_secondary="其他", entities=entities)


def mock_emotion(message: str) -> EmotionAnalysis:
    if _hit(message, ANGRY_WORDS):
        return EmotionAnalysis(emotion="愤怒", trend="up")
    if _hit(message, ANXIOUS_WORDS) or "？" in message or "?" in message:
        return EmotionAnalysis(emotion="焦虑", trend="up")
    return EmotionAnalysis(emotion="平静", trend="flat")


def mock_severity(message: str) -> str:
    """不适程度。顺序：就医/严重词 → obvious → 有症状词 → none。

    医疗词优先，是因为「已就医」本身在文档里就是 L3 的判定依据，程度一定不轻。
    """
    if _hit(message, MEDICAL_WORDS) or _hit(message, SEVERE_WORDS):
        return "severe"
    if _hit(message, OBVIOUS_WORDS):
        return "obvious"
    if _hit(message, SYMPTOM_WORDS):
        return "mild"
    return "none"


def mock_risk(message: str) -> RiskExtraction:
    return RiskExtraction(
        adverse_reaction=_hit(message, SYMPTOM_WORDS),
        severity=mock_severity(message),
        symptoms=_hits(message, SYMPTOM_WORDS),
        medical_visit=_hit(message, MEDICAL_WORDS),
        regulatory_complaint=_hit(message, REGULATORY_WORDS),
    )


def skin_profile(message: str, entities: list[str] | None = None) -> str:
    """从消息/实体中提取「肤质 + 困扰」，生成一句个性化画像。

    同时供真实 prompt（作为 {user_profile} 变量）与 Mock 回复复用，保证两条路径
    都以顾客的具体肤质/困扰为锚点，避免千人一面。
    """
    text = message or ""
    skin: str | None = None
    for key, label in SKIN_TYPE_WORDS:
        if key in text:
            skin = label
            break
    if skin is None:
        for ent in entities or []:
            for key, label in SKIN_TYPE_WORDS:
                if key in str(ent):
                    skin = label
                    break
            if skin:
                break

    concerns: list[str] = []
    for key, label in CONCERN_WORDS:
        if key in text and label not in concerns:
            concerns.append(label)

    parts: list[str] = []
    if skin:
        parts.append(f"肤质：{skin}")
    if concerns:
        parts.append("主要困扰：" + "、".join(concerns))
    return "；".join(parts)


def _personalized_advice(skin: str | None, concerns: list[str]) -> str:
    """按肤质/困扰给一句专业、不越界（不诊断/不荐药/不保证）的护肤建议。"""
    tips: list[str] = []
    if skin == "敏感肌" or "易过敏" in concerns:
        tips.append("优先选择成分简单、无香精酒精的温和修护型产品，帮助强化皮肤屏障")
    if skin == "干性肌肤" or "干燥" in "".join(concerns) or "保湿" in concerns:
        tips.append("注重保湿锁水，可选择含保湿修护成分、质地滋润的产品")
    if skin == "油性肌肤" or any(c in concerns for c in ("长痘", "爆痘", "闭口粉刺", "毛孔粗大", "黑头")):
        tips.append("注意清爽控油与毛孔调理，同时避免过度清洁破坏屏障")
    if any(c in concerns for c in ("暗沉", "提亮肤色", "色斑")):
        tips.append("可关注提亮肤色类成分，并坚持防晒")
    if any(c in concerns for c in ("细纹", "抗老紧致")):
        tips.append("可循序渐进使用抗老紧致类成分，重在长期坚持")
    if not tips:
        tips.append("根据您的肤质选择温和、成分适配的产品，从基础保湿修护做起")
    return "；".join(tips)


def mock_reply(
    risk_level: str,
    evidence_lines: list[str],
    message: str = "",
    entities: list[str] | None = None,
) -> ReplyDraft:
    facts = "；".join(evidence_lines) if evidence_lines else ""

    if risk_level == "L3":
        reply = (
            "非常抱歉给您带来这样的困扰。您反馈的不适情况我们已经记录，"
            "请先停止使用该产品并尽快就医，具体处理请以医生意见为准。"
            "我已为您升级到专员跟进，会尽快与您联系确认后续处理。"
        )
        return ReplyDraft(reply=reply)

    if risk_level in {"L1", "L2"}:
        return ReplyDraft(
            reply=(
                "非常抱歉让您有不舒服的体验。虽然每个人的皮肤反应不同，"
                "但建议您先暂停使用该产品，并把使用部位和出现时间告诉我们，方便我们核对。"
                f"当前系统记录：{facts}。"
            )
        )

    # L0：个性化售前/一般咨询 —— 先共情复述顾客的肤质与困扰，再给专业建议，
    # 而不是千篇一律的爆款式回复。
    profile = skin_profile(message, entities)
    facts_clause = f"另外，已为您核实：{facts}。" if facts else ""
    if profile:
        skin = _skin_of(profile)
        concerns = _concerns_of(profile)
        advice = _personalized_advice(skin, concerns)
        # 把画像渲染成自然语言，避免「肤质：敏感肌」这种机械表述
        who = f"您是{skin}" if skin else "您"
        if concerns:
            ack = f"{who}，目前主要有{'、'.join(concerns)}的困扰"
        else:
            ack = who
        reply = (
            f"理解您的顾虑——{ack}。针对您的情况，建议{advice}。"
            "建议先在耳后或下颌小面积试用，确认无泛红、刺痛等不适后再正常使用；"
            "如不适持续或加重，建议咨询专业皮肤科医生。"
            f"{facts_clause}"
            "方便告诉我您目前正在用的产品和使用感受吗？这样我能给您更贴合的建议。"
        )
    else:
        reply = (
            f"您好，已为您核实：{facts}。" if facts else "您好，"
        ) + "为了给您更贴合的建议，方便先说说您的肤质和主要困扰吗？"
    return ReplyDraft(reply=reply)


def _skin_of(profile: str) -> str | None:
    if "肤质：" not in profile:
        return None
    return profile.split("肤质：", 1)[1].split("；", 1)[0]


def _concerns_of(profile: str) -> list[str]:
    if "主要困扰：" not in profile:
        return []
    return [c for c in profile.split("主要困扰：", 1)[1].split("；", 1)[0].split("、") if c]


def mock_promise(message_text: str) -> PromiseExtraction:
    """从客服消息中抽取承诺候选（关键词规则）。"""
    if "回访" in message_text or "致电" in message_text or "电话" in message_text:
        ptype = "follow_up"
    elif _hit(message_text, REFUND_WORDS):
        ptype = "refund"
    elif _hit(message_text, LOGISTICS_WORDS):
        ptype = "logistics"
    elif "补发" in message_text or "换货" in message_text:
        ptype = "replenishment"
    else:
        ptype = "other"

    due = ""
    for pattern in (
        r"今天\s*\d{1,2}\s*[:点]\s*\d{0,2}\s*前?",
        r"明天(上午|下午|晚上)?",
        r"\d+\s*个?\s*工作日",
        r"\d+\s*小时",
        r"\d+\s*天内?",
    ):
        match = re.search(pattern, message_text)
        if match:
            due = match.group(0).strip()
            break

    has_promise = ptype != "other" or bool(due)
    return PromiseExtraction(
        has_promise=has_promise,
        promise_type=ptype,
        statement=message_text.strip(),
        due_expression=due,
        owner_type="agent",
        confidence=0.6 if has_promise else 0.0,
    )


def mock_vision(images: list[dict]) -> VisionExtraction:
    """图片识别 Mock。

    有真实图片数据（url / b64 / path）时返回确定性的「清晰 / 患处照片」；
    只有占位（如 [图片]）时返回「待识别」，交人工确认 —— 绝不编造图中内容。
    """
    if not images:
        return VisionExtraction()

    first = images[0]
    if any(first.get(key) for key in ("image_url", "image_b64", "image_path")):
        return VisionExtraction(
            image_type="患处照片",
            clarity="清晰",
            batch_no=first.get("batch_no_masked") or first.get("batch_no") or "",
            visible_symptoms=["局部泛红"],
            extra_fields={},
        )
    return VisionExtraction()


def mock_summary(
    events: list[dict],
    messages: list[dict],
    orders: list[dict],
    tickets: list[dict],
    promises: list[dict],
) -> TrajectorySummary:
    """轨迹摘要 Mock：把最近的历史事件标题串成一句，事件 ID 一并保留用于溯源。"""
    lines: list[str] = []
    ids: list[str] = []

    for event in (events or [])[-5:]:
        eid = event.get("event_id") or event.get("id") or ""
        title = event.get("title") or event.get("event_type") or ""
        if title:
            lines.append(str(title))
            if eid:
                ids.append(str(eid))

    if not lines:
        if promises:
            lines.append("存在历史服务承诺")
        elif orders:
            lines.append("存在关联订单")
        else:
            lines.append("暂无跨会话历史轨迹")

    return TrajectorySummary(summary="；".join(lines), relevant_event_ids=ids)


def mock_rewrite(command: str, draft: str, params: dict | None = None) -> RewriteResult:
    """草稿改写 Mock：确定性前缀标注，不调用模型，结果可复现（Task 02/03）。"""
    params = params or {}
    if command == "adjust_tone":
        tone = params.get("tone", "polite")
        return RewriteResult(rewritten=f"（{tone} 语气润色）{draft}")
    return RewriteResult(rewritten=f"（表达已优化）{draft}")
