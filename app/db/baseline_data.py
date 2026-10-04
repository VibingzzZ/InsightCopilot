# 演示基线数据（baseline-v1）：退款 / 不良反应 / 赠品补发 三场景
#
# 固定入口（见开发任务文档）：
#   退款      -> S00005（消费者 魏h**，含历史会话 S00004 与未完成退款承诺）
#   不良反应  -> S00015（消费者 陈x**，已就医触发 L3，等待建单）
#   赠品补发  -> S00159（消费者 姚b**，48 小时补发承诺进入履约雷达）
#
# 时间均以“灌库时刻”为基准做相对偏移，保证任何时候重置后演示状态一致。

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.core.masking import mask_tracking_no
from app.core.time_utils import CHINA_TZ, to_iso

BASELINE_SEED = "baseline-v1"

SCENARIO_SESSION_IDS: dict[str, list[str]] = {
    "refund": ["S00004", "S00005"],
    "adverse_reaction": ["S00015"],
    "gift_resend": ["S00159"],
}


@dataclass
class BaselineData:
    consumers: list[dict[str, Any]] = field(default_factory=list)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    tickets: list[dict[str, Any]] = field(default_factory=list)
    promises: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def all_session_ids(self) -> list[str]:
        return [s["session_id"] for s in self.sessions]


def build_baseline(now: datetime) -> BaselineData:
    """按相对时间构建三场景基线数据。"""
    local_now = now.astimezone(CHINA_TZ)
    data = BaselineData()

    def ts(**delta: float) -> str:
        return to_iso(local_now + timedelta(**delta))

    # ------------------------------------------------------------ 消费者
    data.consumers = [
        {
            "consumer_id": "C00005",
            "display_name_masked": "魏h**",
            "risk_level": "L2",
            "risk_note": "存在历史退款承诺未完成，注意重复进线",
        },
        {
            "consumer_id": "C00015",
            "display_name_masked": "陈x**",
            "risk_level": "L0",
            "risk_note": None,
        },
        {
            "consumer_id": "C00159",
            "display_name_masked": "姚b**",
            "risk_level": "L1",
            "risk_note": "赠品补发处理中",
        },
    ]

    # ------------------------------------------------------------ 会话
    data.sessions = [
        {
            "session_id": "S00004",
            "consumer_id": "C00005",
            "store_name": "知微美妆官方旗舰店",
            "scene_major": "售后",
            "scene_minor": "退款",
            "status": "closed",
            "started_at": ts(days=-6, hours=-1),
            "ended_at": ts(days=-6),
            "last_message_at": ts(days=-6),
            "intent_primary": "退款进度咨询",
            "intent_secondary": "退款未到账",
            "emotion": "concerned",
            "risk_level": "L2",
            "summary": "消费者咨询退款未到账，客服登记 3 个工作日退款核实承诺。",
            "unresolved_count": 1,
        },
        {
            "session_id": "S00005",
            "consumer_id": "C00005",
            "store_name": "知微美妆官方旗舰店",
            "scene_major": "售后",
            "scene_minor": "退款核实",
            "status": "open",
            "started_at": ts(minutes=-35),
            "ended_at": None,
            "last_message_at": ts(minutes=-10),
            "intent_primary": "退款进度咨询",
            "intent_secondary": "历史承诺未履约",
            "emotion": "angry",
            "risk_level": "L2",
            "summary": "消费者再次进线催退款，提及投诉倾向，历史承诺已超时。",
            "unresolved_count": 1,
        },
        {
            "session_id": "S00015",
            "consumer_id": "C00015",
            "store_name": "知微美妆官方旗舰店",
            "scene_major": "售后",
            "scene_minor": "不良反应",
            "status": "open",
            "started_at": ts(hours=-2),
            "ended_at": None,
            "last_message_at": ts(minutes=-15),
            "intent_primary": "过敏不适处理",
            "intent_secondary": "已就医求助",
            "emotion": "urgent",
            "risk_level": "L3",
            "summary": "消费者使用精华后出现泛红刺痛，已就医并上传门诊资料。",
            "unresolved_count": 1,
        },
        {
            "session_id": "S00159",
            "consumer_id": "C00159",
            "store_name": "知微美妆官方旗舰店",
            "scene_major": "售后",
            "scene_minor": "赠品补发",
            "status": "open",
            "started_at": ts(hours=-26),
            "ended_at": None,
            "last_message_at": ts(hours=-24),
            "intent_primary": "赠品漏发",
            "intent_secondary": "补发进度",
            "emotion": "concerned",
            "risk_level": "L1",
            "summary": "消费者反馈赠品洁面仪漏发，客服承诺 48 小时内补发并同步物流单号。",
            "unresolved_count": 1,
        },
    ]

    # ------------------------------------------------------------ 消息
    data.messages = [
        # S00004 历史退款会话
        _msg("m-s4-1", "S00004", 1, ts(days=-6, hours=-1), "buyer", "你好，我下单的面霜退款一直没到，麻烦帮我查一下"),
        _msg(
            "m-s4-2",
            "S00004",
            2,
            ts(days=-6, hours=-1, minutes=8),
            "agent",
            "您好，非常抱歉让您久等，我先帮您核实订单的退款进度。",
        ),
        _msg(
            "m-s4-3",
            "S00004",
            3,
            ts(days=-6, minutes=-30),
            "agent",
            "已为您登记退款核实，承诺3个工作日内给您明确结果，请放心。",
        ),
        _msg("m-s4-4", "S00004", 4, ts(days=-6, minutes=-20), "buyer", "好的，那我等你们消息。"),
        _msg("m-s4-5", "S00004", 5, ts(days=-6), "system", "[系统] 退款核实承诺已进入履约队列，责任人 G002。"),
        # S00005 再次进线
        _msg(
            "m-s5-1", "S00005", 1, ts(minutes=-30), "system", "[系统] 消费者再次进线，历史会话 S00004 存在未完成承诺。"
        ),
        _msg(
            "m-s5-2",
            "S00005",
            2,
            ts(minutes=-12),
            "buyer",
            "上次答应处理的退款怎么还没到，都一个礼拜了一分没到，急死了",
            is_target=True,
        ),
        _msg("m-s5-3", "S00005", 3, ts(minutes=-10), "buyer", "你们再不给个说法我只能投诉了"),
        # S00015 不良反应
        _msg("m-s15-1", "S00015", 1, ts(hours=-2), "buyer", "用了你们家的舒缓修护精华两天，脸上又红又刺痛"),
        _msg(
            "m-s15-2",
            "S00015",
            2,
            ts(hours=-1),
            "buyer",
            "今天去医院看过了，医生说是接触性皮炎，开了药",
            is_target=True,
        ),
        _msg(
            "m-s15-3",
            "S00015",
            3,
            ts(minutes=-50),
            "buyer",
            "[图片] 医院门诊单据",
            content_type="image",
            image_path="data/media/S00015_outpatient_note.jpg",
        ),
        _msg(
            "m-s15-4",
            "S00015",
            4,
            ts(minutes=-15),
            "agent",
            "非常抱歉给您带来不适，我马上为您升级处理并安排专员跟进，请您先停用该产品。",
        ),
        # S00159 赠品补发
        _msg(
            "m-s159-1",
            "S00159",
            1,
            ts(hours=-26),
            "buyer",
            "我收到货了，但是说好的赠品洁面仪没有，只有正装",
            is_target=True,
        ),
        _msg(
            "m-s159-2",
            "S00159",
            2,
            ts(hours=-25),
            "agent",
            "非常抱歉，我马上为您核实仓库发货情况，48小时内给您完成补发并同步物流单号。",
        ),
        _msg("m-s159-3", "S00159", 3, ts(hours=-24), "buyer", "行，那我等物流单号。"),
        _msg("m-s159-4", "S00159", 4, ts(hours=-24), "system", "[系统] 补发工单 T00159 已创建，等待仓库处理。"),
    ]

    # ------------------------------------------------------------ 订单
    data.orders = [
        {
            "order_id": "O00004",
            "order_no": "O00004",
            "session_id": "S00004",
            "consumer_id": "C00005",
            "store_name": "知微美妆官方旗舰店",
            "sku": "SKU-CREAM-50",
            "product_name": "光透修护面霜 50ml",
            "quantity": 1,
            "unit_price_cent": 19800,
            "paid_amount_cent": 19800,
            "order_status": "refunding",
            "ordered_at": ts(days=-7),
            "paid_at": ts(days=-7, minutes=5),
            "shipped_at": ts(days=-6, hours=-20),
            "carrier": "中通快递",
            "tracking_no_masked": mask_tracking_no("78912345678901"),
            "shipping_province": "浙江省",
            "shipping_city": "杭州市",
            "gift_description": "小样三件套",
            "buyer_note_redacted": "请尽快退款",
        },
        {
            "order_id": "O00015",
            "order_no": "O00015",
            "session_id": "S00015",
            "consumer_id": "C00015",
            "store_name": "知微美妆官方旗舰店",
            "sku": "SKU-ESSENCE-30",
            "product_name": "舒缓修护精华 30ml",
            "quantity": 1,
            "unit_price_cent": 23900,
            "paid_amount_cent": 23900,
            "order_status": "received",
            "ordered_at": ts(days=-10),
            "paid_at": ts(days=-10, minutes=3),
            "shipped_at": ts(days=-9),
            "carrier": "圆通速递",
            "tracking_no_masked": mask_tracking_no("YT4520128890012"),
            "shipping_province": "江苏省",
            "shipping_city": "南京市",
            "gift_description": "旅行装小样",
            "buyer_note_redacted": "敏感肌，请确保正品",
        },
        {
            "order_id": "O00159",
            "order_no": "O00159",
            "session_id": "S00159",
            "consumer_id": "C00159",
            "store_name": "知微美妆官方旗舰店",
            "sku": "SKU-CLEAN-SET",
            "product_name": "氨基酸洁面仪套装",
            "quantity": 1,
            "unit_price_cent": 15600,
            "paid_amount_cent": 15600,
            "order_status": "shipped",
            "ordered_at": ts(days=-3),
            "paid_at": ts(days=-3, minutes=2),
            "shipped_at": ts(days=-2),
            "carrier": "韵达快递",
            "tracking_no_masked": mask_tracking_no("YD3312987765432"),
            "shipping_province": "广东省",
            "shipping_city": "深圳市",
            "gift_description": "赠品洁面仪 x1",
            "buyer_note_redacted": "",
        },
    ]

    # ------------------------------------------------------------ 工单
    data.tickets = [
        {
            "ticket_id": "T00004",
            "ticket_no": "T00004",
            "ticket_type": "offline_payment",
            "session_id": "S00004",
            "consumer_id": "C00005",
            "order_id": "O00004",
            "reason": "退款迟迟未到账，需核实打款进度",
            "priority": "urgent",
            "status": "in_progress",
            "assignee": "G002",
            "created_at": ts(days=-6, hours=-2),
            "detail": {
                "payment_type": "退款差额",
                "refund_reason_type": "退款核实",
                "refund_amount_cent": 19800,
                "related_tracking_masked": "中通 ****8901",
                "transfer_status": "处理中",
                "alipay_name_masked": "魏**",
                "alipay_account_masked": "13***89",
            },
        },
        {
            "ticket_id": "T00159",
            "ticket_no": "T00159",
            "ticket_type": "replenishment_exchange",
            "session_id": "S00159",
            "consumer_id": "C00159",
            "order_id": "O00159",
            "reason": "赠品洁面仪漏发，需补发",
            "priority": "normal",
            "status": "pending",
            "assignee": "G001",
            "created_at": ts(hours=-24),
            "detail": {
                "ship_sku": "SKU-GIFT-CM1",
                "ship_product_name": "洁面仪（赠品）",
                "quantity": 1,
                "warehouse": "华南仓",
                "replacement_tracking_masked": None,
                "expedite": False,
            },
        },
    ]

    # ------------------------------------------------------------ 服务承诺
    data.promises = [
        {
            "promise_id": "P-BASE-0001",
            "consumer_id": "C00005",
            "session_id": "S00004",
            "source_message_id": "m-s4-3",
            "promise_type": "refund",
            "statement": "3个工作日内完成退款核实并回复明确结果",
            "owner_type": "agent",
            "owner_id": "G002",
            "due_at": ts(hours=-26),
            "status": "active",
            "verification_type": "ticket_completed",
            "verification_ref": "T00004",
            "confirmed_by": "G002",
            "confirmed_at": ts(days=-6),
        },
        {
            "promise_id": "P-BASE-0002",
            "consumer_id": "C00159",
            "session_id": "S00159",
            "source_message_id": "m-s159-2",
            "promise_type": "replenishment",
            "statement": "48小时内完成赠品补发并同步物流单号",
            "owner_type": "agent",
            "owner_id": "G001",
            "due_at": ts(hours=20),
            "status": "active",
            "verification_type": "ticket_completed",
            "verification_ref": "T00159",
            "confirmed_by": "G001",
            "confirmed_at": ts(hours=-25),
        },
        {
            "promise_id": "P-BASE-0003",
            "consumer_id": "C00159",
            "session_id": "S00159",
            "source_message_id": "m-s159-2",
            "promise_type": "follow_up",
            "statement": "今天18:00前回复仓库核实结果",
            "owner_type": "agent",
            "owner_id": "G001",
            "due_at": ts(days=-1, hours=6),
            "status": "fulfilled",
            "verification_type": "message_sent",
            "verification_ref": "m-s159-2",
            "confirmed_by": "G001",
            "confirmed_at": ts(days=-1, hours=8),
            "fulfilled_at": ts(days=-1, hours=6),
        },
    ]

    # ------------------------------------------------------------ 时间线事件
    data.events = [
        _event(
            "C00005",
            "S00004",
            ticket_id="T00004",
            event_type="ticket_status",
            occurred_at=ts(days=-6, hours=-2),
            title="线下打款工单创建",
            content="退款核实工单 T00004 已创建，责任人 G002。",
            source_type="ticket",
            source_id="T00004",
        ),
        _event(
            "C00005",
            "S00004",
            event_type="promise",
            occurred_at=ts(days=-6, minutes=-30),
            title="退款核实承诺登记",
            content="承诺3个工作日内完成退款核实并回复明确结果。",
            source_type="chat",
            source_id="m-s4-3",
            evidence=["m-s4-3"],
        ),
        _event(
            "C00005",
            "S00005",
            event_type="message",
            occurred_at=ts(minutes=-12),
            title="消费者再次进线催办退款",
            content="消费者反馈退款仍未到账，存在投诉倾向。",
            source_type="chat",
            source_id="m-s5-2",
            evidence=["m-s5-2", "m-s5-3"],
        ),
        _event(
            "C00015",
            "S00015",
            event_type="message",
            occurred_at=ts(hours=-1),
            title="消费者反馈已就医",
            content="消费者上传门诊资料图片，等待人工确认处理。",
            source_type="chat",
            source_id="m-s15-2",
            evidence=["m-s15-2", "m-s15-3"],
            order_id="O00015",
        ),
        _event(
            "C00159",
            "S00159",
            ticket_id="T00159",
            event_type="ticket_status",
            occurred_at=ts(hours=-24),
            title="补发工单创建",
            content="赠品补发工单 T00159 已创建，等待仓库处理。",
            source_type="ticket",
            source_id="T00159",
            order_id="O00159",
        ),
        _event(
            "C00159",
            "S00159",
            event_type="promise",
            occurred_at=ts(hours=-25),
            title="补发承诺登记",
            content="承诺48小时内完成赠品补发并同步物流单号。",
            source_type="chat",
            source_id="m-s159-2",
            evidence=["m-s159-2"],
        ),
    ]

    return data


def _msg(
    message_id: str,
    session_id: str,
    seq_no: int,
    sent_at: str,
    role: str,
    text: str,
    *,
    content_type: str = "text",
    image_path: str | None = None,
    is_target: bool = False,
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "session_id": session_id,
        "seq_no": seq_no,
        "sent_at": sent_at,
        "role": role,
        "sender_label": {"buyer": "消费者", "agent": "客服", "system": "系统"}.get(role, role),
        "content_type": content_type,
        "message_text": text,
        "image_path": image_path,
        "is_target_buyer_message": is_target,
    }


def _event(
    consumer_id: str,
    session_id: str,
    *,
    event_type: str,
    occurred_at: str,
    title: str,
    content: str,
    source_type: str,
    source_id: str,
    evidence: list[str] | None = None,
    ticket_id: str | None = None,
    order_id: str | None = None,
) -> dict[str, Any]:
    return {
        "consumer_id": consumer_id,
        "session_id": session_id,
        "ticket_id": ticket_id,
        "order_id": order_id,
        "event_type": event_type,
        "occurred_at": occurred_at,
        "actor_type": "system" if event_type != "message" else "buyer",
        "title": title,
        "content": content,
        "source_type": source_type,
        "source_id": source_id,
        "evidence_message_ids": evidence or [],
    }
