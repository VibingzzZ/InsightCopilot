from app.agent.state import CustomerState

SEVERE_SYMPTOMS = ("呼吸困难", "喘不上气", "眼部", "眼睛肿", "住院", "晕倒")


def risk_engine_node(state: CustomerState) -> dict:
    risk = state["risk"]
    severity = risk.get("severity", "none")
    emotion = state["emotion"]
    strong_emotion = emotion in {"愤怒", "急切", "不满"}
    reasons: list[str] = []

    # L3：已就医 / 监管投诉 / 严重程度，任一命中直接最高级（文档 §6.3）
    if risk["medical_visit"]:
        reasons.append("消费者已就医")
    if risk["regulatory_complaint"]:
        reasons.append("提及监管投诉或舆情曝光")
    symptoms_text = " ".join(risk["symptoms"])
    if severity == "severe" or any(word in symptoms_text for word in SEVERE_SYMPTOMS):
        reasons.append("症状较严重")

    if reasons:
        return {"risk_level": "L3", "risk_reasons": reasons}

    # L2：范围扩大/持续加重/明显红肿，或出现不良反应且情绪强烈
    if severity == "obvious":
        reasons.append("症状明显（范围扩大或持续加重）")
    elif risk["adverse_reaction"] and strong_emotion:
        reasons.append("出现不良反应且情绪强烈")

    if reasons:
        return {"risk_level": "L2", "risk_reasons": reasons}

    # L1：轻微不适且未加重
    if risk["adverse_reaction"] or severity == "mild":
        return {"risk_level": "L1", "risk_reasons": ["出现轻微不良反应，尚未加重"]}

    # L0：普通咨询
    return {"risk_level": "L0", "risk_reasons": []}
