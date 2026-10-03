"""Agent 层对外入口。

只暴露两个纯函数：
  run_copilot(request)     —— 对应 GET /api/sessions/{id}/copilot
  extract_promises(req)    —— 对应 POST /api/promises/extract

两个函数都不查库、不调外部接口，只消费后端预组装好的上下文。

本地演示：
  python -m app.agent.run --mock              # 断网/无 Key 也能跑通
  python -m app.agent.run --case 不良反应
  python -m app.agent.run --promise "明天上午给您退款"
"""

import argparse
import json
import sys
from typing import Any

from app.agent.graph import graph
from app.agent.nodes.promise import extract_promise_candidate
from app.agent.schemas.contract import (
    AdverseAssessment,
    AgentMode,
    CopilotInsight,
    CopilotRequest,
    CopilotResult,
    FactCheckResult,
    PromiseExtractRequest,
    PromiseExtractResult,
)
from app.agent.state import CustomerState

# 三个样例契约。后端照这份结构预组装上下文即可 —— 字段名就是对接口径。
CASES: dict[str, dict[str, Any]] = {
    "退款": {
        "request": CopilotRequest(
            session_id="S-DEMO-001",
            customer_name_masked="李**",
            current_message="我上周买的那瓶精华，退款怎么还没到账？都三天了",
            messages=[
                {
                    "message_id": "M-001",
                    "sender_type": "customer",
                    "message_text": "我上周买的那瓶精华，退款怎么还没到账？都三天了",
                    "content_type": "text",
                }
            ],
            orders=[
                {
                    "order_id": "202509120001",
                    "order_status": "已签收",
                    "product_name": "光感修护精华 30ml",
                    "refund_status": "退款处理中",
                    "paid_amount": "299.00",
                }
            ],
            tickets=[],
        )
    },
    "物流": {
        "request": CopilotRequest(
            session_id="S-DEMO-002",
            customer_name_masked="王**",
            current_message="我的快递三天没动静了，到底什么时候能到？",
            messages=[
                {
                    "message_id": "M-101",
                    "sender_type": "customer",
                    "message_text": "我的快递三天没动静了，到底什么时候能到？",
                    "content_type": "text",
                }
            ],
            orders=[
                {
                    "order_id": "202509150007",
                    "order_status": "已发货",
                    "product_name": "氨基酸洁面乳 120g",
                    "tracking_no_masked": "SF****7890",
                }
            ],
            tickets=[],
        )
    },
    "不良反应": {
        "request": CopilotRequest(
            session_id="S-DEMO-003",
            customer_name_masked="张**",
            current_message="用了你们的面霜脸特别红，很疼，已经去医院了",
            messages=[
                {
                    "message_id": "M-201",
                    "sender_type": "customer",
                    "message_text": "用了你们的面霜脸特别红，很疼，已经去医院了",
                    "content_type": "text",
                },
                {
                    "message_id": "M-202",
                    "sender_type": "customer",
                    "message_text": "[图片]",
                    "content_type": "image",
                },
            ],
            orders=[
                {
                    "order_id": "202509010033",
                    "order_status": "已签收",
                    "product_name": "舒缓修护面霜 50g",
                    "batch_no_masked": "B2409**",
                }
            ],
            tickets=[],
        )
    },
}


def _make_state(request: CopilotRequest) -> CustomerState:
    """把请求铺成完整的图状态。

    TypedDict 缺 key 会在节点里 KeyError，所以这里**每个 key 都必须出现**。
    """
    return {
        # 输入层
        "session_id": request.session_id,
        "customer_name_masked": request.customer_name_masked or "",
        "current_message": request.current_message,
        "messages": request.messages,
        "orders": request.orders,
        "tickets": request.tickets,
        "promises": request.promises,
        "mode": request.mode,
        # 理解层
        "intent": {},
        "emotion": "unknown",
        "emotion_trend": "flat",
        # 风险层
        "risk": {
            "adverse_reaction": False,
            "severity": "none",
            "symptoms": [],
            "medical_visit": False,
            "regulatory_complaint": False,
        },
        "risk_level": "L0",
        "risk_reasons": [],
        # 数据层
        "linked_order": {},
        "linked_tickets": [],
        # 证据层
        "evidence": [],
        # 处置层
        "missing_fields": [],
        "suggested_actions": [],
        "adverse": None,
        # 表达层
        "reply_draft": "",
        "fact_check": {"status": "pass", "unverified_claims": [], "blocked": False},
        # 可观测性
        "degraded": False,
        "model_route": "mock",
    }


def run_copilot(request: CopilotRequest) -> CopilotResult:
    """跑一遍副驾链路。不改变任何业务状态。"""
    final = graph.invoke(_make_state(request))
    intent = final.get("intent") or {}
    adverse = final.get("adverse")

    return CopilotResult(
        session_id=request.session_id,
        insight=CopilotInsight(
            intent_primary=intent.get("primary"),
            intent_secondary=intent.get("secondary"),
            entities=intent.get("entities") or [],
            emotion=final.get("emotion", "unknown"),
            emotion_trend=final.get("emotion_trend", "flat"),
            risk_level=final.get("risk_level", "L0"),
            risk_reasons=final.get("risk_reasons") or [],
            missing_fields=final.get("missing_fields") or [],
            suggested_actions=final.get("suggested_actions") or [],
            evidence=final.get("evidence") or [],
            model_route=final.get("model_route", "mock"),
            degraded=bool(final.get("degraded")),
        ),
        draft_reply=final.get("reply_draft") or None,
        adverse=AdverseAssessment(**adverse) if adverse else None,
        fact_check=FactCheckResult(**(final.get("fact_check") or {})),
    )


def extract_promises(req: PromiseExtractRequest) -> PromiseExtractResult:
    """抽取客服消息里的服务承诺候选。只给候选，建单由人工确认。"""
    return extract_promise_candidate(req)


def _print_case(name: str, result: CopilotResult) -> None:
    insight = result.insight
    print(f"\n{'=' * 60}")
    print(f"[{name}] session={result.session_id}  model_route={insight.model_route}  degraded={insight.degraded}")
    print(f"  意图：{insight.intent_primary} / {insight.intent_secondary}  实体：{insight.entities}")
    print(f"  情绪：{insight.emotion}（{insight.emotion_trend}）")
    print(f"  风险：{insight.risk_level}  依据：{insight.risk_reasons}")
    print(f"  缺失字段：{insight.missing_fields}")
    print(f"  建议动作：{insight.suggested_actions}")
    for item in insight.evidence:
        print(f"  证据[{item.source_type}:{item.source_id}] {item.quote}")
    if result.adverse:
        print(f"  不良反应：grade={result.adverse.grade} 已就医={result.adverse.medical_visit}")
        print(f"  工单草稿：{result.adverse.ticket_draft}")
    print(f"  事实校验：{result.fact_check.status} {result.fact_check.unverified_claims}")
    print(f"  回复草稿：{result.draft_reply}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="知微客服副驾 Agent 本地演示")
    parser.add_argument("--mock", action="store_true", help="强制走确定性 Mock，完全不调用模型")
    parser.add_argument("--case", default=None, help="只跑名字包含该关键字的样例")
    parser.add_argument("--promise", default=None, help="额外演示一条承诺抽取")
    parser.add_argument("--json", action="store_true", help="改为打印完整 JSON")
    args = parser.parse_args(argv)

    mode: AgentMode = "mock" if args.mock else "auto"
    names = [name for name in CASES if not args.case or args.case in name]
    if not names:
        print(f"没有匹配 {args.case!r} 的样例，可选：{'、'.join(CASES)}", file=sys.stderr)
        return 1

    for name in names:
        request = CASES[name]["request"].model_copy(update={"mode": mode})
        result = run_copilot(request)
        if args.json:
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
        else:
            _print_case(name, result)

    if args.promise:
        promise_result = extract_promises(
            PromiseExtractRequest(
                session_id="S-DEMO-001",
                message_id="M-900",
                message_text=args.promise,
                mode=mode,
            )
        )
        print(f"\n{'=' * 60}")
        print(f"[承诺抽取] {args.promise}")
        print(json.dumps(promise_result.model_dump(), ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
