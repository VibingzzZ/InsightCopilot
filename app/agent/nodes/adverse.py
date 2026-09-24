"""不良反应专项节点（L1 / L2 / L3）。

纯代码，不调用模型。只产出结构化评估与工单草稿，**不建单、不改业务状态**。

边界：这是服务风险分级和流程辅助，不做医学诊断，不根据图片判断疾病，
不给出用药建议，也不能替代医生意见。
"""

from collections.abc import Callable
from typing import cast

from app.agent.schemas.contract import AdverseAssessment, AdverseGrade
from app.agent.state import CustomerState
from app.agent.time import normalize_due
from app.agent.tools.order import batch_no_of, product_name_of

# 从聊天里判断「这个字段是否已经被说过」，说过就不再重复询问
_AREA_WORDS = ("脸", "额头", "脸颊", "脖子", "下巴", "眼周", "嘴角", "手", "手臂", "全身", "身体")
_OCCURRENCE_WORDS = ("昨天", "今天", "前天", "几天", "一周", "两天", "三天", "刚", "小时", "天前")
_STOPPED_WORDS = ("停用", "没用了", "不敢用", "已经不用", "暂停使用", "没用过")

_GRADES = ("L1", "L2", "L3")


def _texts(state: CustomerState) -> list[str]:
    """历史消息 + 当前消息的文本集合，只用于判断字段是否已知。"""
    texts: list[str] = []

    for message in state.get("messages") or []:
        value = message.get("message_text") or message.get("content") or ""
        if value:
            texts.append(str(value))

    if state.get("current_message"):
        texts.append(state["current_message"])

    return texts


def _mentions(state: CustomerState, words: tuple[str, ...]) -> bool:
    return any(any(word in text for word in words) for text in _texts(state))


def _has_image(state: CustomerState) -> bool:
    return any((message.get("content_type") == "image") for message in (state.get("messages") or []))


def _has_batch_no(state: CustomerState) -> bool:
    return bool(batch_no_of(state.get("linked_order") or {}))


# (缺失字段名, 是否已知) —— 顺序即客服的询问顺序，只把未知的列进 missing_fields
_FIELD_CHECKS: tuple[tuple[str, Callable[[CustomerState], bool]], ...] = (
    ("产品批次号", _has_batch_no),
    ("使用部位", lambda state: _mentions(state, _AREA_WORDS)),
    ("症状出现时间", lambda state: _mentions(state, _OCCURRENCE_WORDS)),
    ("是否停止使用", lambda state: _mentions(state, _STOPPED_WORDS)),
    ("是否就医", lambda state: bool(state["risk"].get("medical_visit"))),
    ("图片或门诊资料", _has_image),
)


def _missing_fields(state: CustomerState) -> list[str]:
    return [label for label, is_known in _FIELD_CHECKS if not is_known(state)]


def _build_actions(grade: str) -> list[str]:
    if grade == "L3":
        return [
            "立即升级主管与不良反应专项团队",
            "创建不良反应工单（紧急）",
            "安排次日上午回访",
            "限制普通客服自由回复，由专员对接",
        ]
    if grade == "L2":
        return [
            "创建不良反应工单（高优先级）",
            "升级不良反应专员",
            "安排 48 小时内回访",
        ]
    return ["登记普通回访任务", "建议消费者暂停使用并补充使用部位与出现时间"]


def _build_ticket_draft(state: CustomerState, grade: str) -> dict:
    """生成 CREATE_TICKET 的 draft_payload。只预填已知字段，未知的留给客服。"""
    risk = state["risk"]
    order = state.get("linked_order") or {}

    priority = "critical" if grade == "L3" else "urgent"
    # 回访时间来自确定性时间服务：L3 依据演示脚本「次日上午回访」，L2 取 48 小时
    follow_up_expression = "明天上午" if grade == "L3" else "48小时"
    follow_up_due_at, _ = normalize_due(follow_up_expression)

    draft: dict = {
        "ticket_type": "adverse_reaction",
        "priority": priority,
        "symptom_summary": _symptom_summary(state),
        "sought_medical_help": bool(risk.get("medical_visit")),
        "follow_up_due_at": follow_up_due_at,
    }

    if product_name_of(order):
        draft["product_name"] = product_name_of(order)
    if batch_no_of(order):
        draft["batch_no_masked"] = batch_no_of(order)

    return draft


def _symptom_summary(state: CustomerState) -> str:
    symptoms = state["risk"].get("symptoms") or []
    return "、".join(symptoms) if symptoms else "消费者自述不适"


def _safe_reply(grade: str, symptom_summary: str, product_name: str) -> str:
    """规则化处置话术：只描述可见现象和服务动作，不给诊断和用药建议。"""
    if grade == "L3":
        return (
            f"非常抱歉给您带来这样的困扰。您反馈的{symptom_summary}情况请您优先就医，"
            f"具体处理请以医生意见为准。我已为您升级主管和专项团队，会持续跟进您的处理进展。"
        )
    if grade == "L2":
        return (
            f"非常抱歉给您带来不适。您反馈的{symptom_summary}我们已经记录，"
            f"建议您暂停使用{product_name}并及时寻求专业医疗帮助，具体处理请以医生意见为准。"
            f"我已为您升级到专员跟进。"
        )
    return (
        f"非常抱歉让您有不舒服的体验。关于您提到的{symptom_summary}，"
        f"建议您先暂停使用{product_name}，并把使用部位和出现时间告诉我们，方便我们核对。"
        f"我会为您登记跟进。"
    )


def adverse_node(state: CustomerState) -> dict:
    level = state.get("risk_level", "L0")
    if level not in _GRADES:
        return {}
    # mypy 不会从 `in` 判断里收窄 str，这里显式声明
    grade = cast(AdverseGrade, level)

    product_name = product_name_of(state.get("linked_order") or {}) or "该产品"
    missing = _missing_fields(state)
    actions = _build_actions(grade)
    symptom_summary = _symptom_summary(state)

    assessment = AdverseAssessment(
        grade=grade,
        symptom_summary=symptom_summary,
        medical_visit=bool(state["risk"].get("medical_visit")),
        stopped_use=None,  # 未知就留空，由客服确认，不猜
        missing_fields=missing,
        ticket_draft=None if grade == "L1" else _build_ticket_draft(state, grade),
        safe_reply=_safe_reply(grade, symptom_summary, product_name),
        suggested_actions=actions,
    )

    return {
        "adverse": assessment.model_dump(),
        "missing_fields": missing,
        "suggested_actions": actions,
    }
