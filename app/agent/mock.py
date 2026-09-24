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
    RiskExtraction,
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

_ORDER_NO_RE = re.compile(r"\d{6,}")


def _hit(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _hits(text: str, words: tuple[str, ...]) -> list[str]:
    return [word for word in words if word in text]


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


def mock_reply(risk_level: str, evidence_lines: list[str]) -> ReplyDraft:
    facts = "；".join(evidence_lines) if evidence_lines else "暂无系统可核验的事实"

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

    return ReplyDraft(reply=f"您好，已为您核实：{facts}。请问还需要我为您做些什么？")


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
