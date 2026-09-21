from app.agent.state import CustomerState


def risk_engine_node(state: CustomerState) -> dict:
    risk = state["risk"]

    # 业务规则：这里有不良反应 + 已就医 → 高风险
    if risk["adverse_reaction"] and risk["medical_visit"]:
        risk_level = "high"
    elif risk["adverse_reaction"]:
        risk_level = "medium"
    else:
        risk_level = "normal"

    return {"risk_level": risk_level}