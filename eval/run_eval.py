"""InsightCopilot · Agent 评测集 Harness（骨架）

用法：
    # 跑全部样例（直接调 LangGraph，无需起服务）
    uv run python eval/run_eval.py

    # 只跑某个场景 + 只看前 2 条（快速验证）
    uv run python eval/run_eval.py --cases 不良反应 --limit 2

    # 额外用 LLM 给回复质量打分（会多烧一点 token）
    uv run python eval/run_eval.py --judge

设计要点：
- Runner 直接 `graph.invoke(_make_state(req))` 拿**完整 final state**，
  因此能拿到 triage 的原始 `risk` 全字段（adverse_reaction/severity/...），
  而 `run_copilot` 的 CopilotResult 只暴露 risk_level，不够评测安全维度。
- 成本直接读 `cost.session_totals(session_id)`，复用已落地的成本功能。
- 评分分四块：① 意图/情绪（精确匹配）② 风险（布尔 + severity 序数）
  ③ 回复质量（规则 must_contain/must_not，--judge 时追加 LLM 1-5）
  ④ 成本效率（token/调用次数/降级占比）。
- 每条 case 用自身 id 当 session_id，成本天然隔离，互不影响。

你后续要扩的：往 eval_cases.jsonl 里加 case；调 score_* 里的阈值/rubric；
细化 llm_judge_reply 的裁判 prompt。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# 让脚本无论从项目根还是作为模块运行，都能 import 到 app 包
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# —— 项目内部依赖（需在项目 venv 下运行）——
from app.agent import cost  # noqa: E402
from app.agent.graph import graph  # noqa: E402
from app.agent.run import _make_state  # noqa: E402
from app.agent.schemas.contract import CopilotRequest  # noqa: E402

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "eval_cases.jsonl"
DEFAULT_REPORT = HERE / "report.md"

# severity 序数：用于风险分级精度评分
SEVERITY_ORDER = {"none": 0, "mild": 1, "obvious": 2, "severe": 3}


# --------------------------------------------------------------------------- #
# 1. 加载用例
# --------------------------------------------------------------------------- #
def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"[用例格式错误] {path.name} 第 {ln} 行: {exc}") from None
    if not cases:
        raise SystemExit(f"[空用例集] {path} 没有任何 case")
    return cases


# --------------------------------------------------------------------------- #
# 2. 构造请求 + 跑图
# --------------------------------------------------------------------------- #
def build_request(case: dict[str, Any]) -> CopilotRequest:
    setup = case.get("setup") or {}
    orders = setup.get("orders") or []
    messages = setup.get("messages") or []
    if not messages:
        messages = [
            {
                "message_id": f"M-{case['id']}",
                "sender_type": "customer",
                "message_text": case["input"],
                "content_type": "text",
            }
        ]
    return CopilotRequest(
        session_id=case["id"],
        current_message=case["input"],
        customer_name_masked="消费者",
        messages=messages,
        orders=orders,
        tickets=setup.get("tickets") or [],
        events=setup.get("events") or [],
        promises=setup.get("promises") or [],
        mode="auto",
    )


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """跑一条 case，返回 Agent 真实输出（actual）。"""
    req = build_request(case)
    cost.set_session(req.session_id)
    try:
        final = graph.invoke(_make_state(req))
    finally:
        cost.set_session(None)

    intent = final.get("intent") or {}
    risk = final.get("risk") or {}
    totals = cost.session_totals(req.session_id)

    return {
        "session_id": req.session_id,
        "intent_primary": intent.get("primary"),
        "intent_secondary": intent.get("secondary"),
        "entities": intent.get("entities") or [],
        "emotion": final.get("emotion"),
        "emotion_trend": final.get("emotion_trend"),
        "risk": {
            "adverse_reaction": bool(risk.get("adverse_reaction", False)),
            "severity": risk.get("severity", "none"),
            "medical_visit": bool(risk.get("medical_visit", False)),
            "regulatory_complaint": bool(risk.get("regulatory_complaint", False)),
        },
        "reply": (final.get("reply_draft") or "").strip(),
        "cost": {
            "total_tokens": totals.get("total_tokens", 0),
            "calls": totals.get("calls", 0),
            "cost_yuan": totals.get("cost_yuan", 0.0),
            "degraded": totals.get("degraded", 0),
        },
    }


# --------------------------------------------------------------------------- #
# 3. 评分（你主要调这里）
# --------------------------------------------------------------------------- #
def _f1(pred: list[str], exp: list[str]) -> float:
    """实体 F1：采用**包含匹配**，缓解金标准粒度（如「精华」）与模型细粒度
    （如「光感修护精华 30ml」）不一致导致的误判——只要一个包含另一个即算命中。
    仍同时看 precision / recall，避免模型乱抽刷分。
    """
    p = [x.strip().lower() for x in pred if x.strip()]
    e = [x.strip().lower() for x in exp if x.strip()]
    if not p and not e:
        return 1.0
    if not p or not e:
        return 0.0

    def _hit(a: str, b: str) -> bool:
        return a in b or b in a

    recall = sum(1 for x in e if any(_hit(x, y) for y in p)) / len(e)
    precision = sum(1 for y in p if any(_hit(y, x) for x in e)) / len(p)
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 3)


# 用户核心诉求关键词：期望 secondary 里出现这些词，才算"抓住了二级诉求"
_APPEAL_KEYWORDS = ["退款", "退货", "赔偿", "赔付", "投诉", "换货", "曝光", "补发", "问责"]


def _secondary_covers(pred_secondary: str | None, exp_secondary: str | None) -> float:
    """验证模型输出的二级意图是否覆盖了期望中的核心诉求。

    期望未给 secondary 时返回 1.0（不参与扣分）；否则检查期望里出现的
    诉求关键词是否都被模型输出涵盖。无明确关键词时退化为子串互含。
    """
    if not exp_secondary:
        return 1.0
    pred = (pred_secondary or "").lower()
    exp = exp_secondary.lower()
    required = [k for k in _APPEAL_KEYWORDS if k in exp]
    if not required:
        return 1.0 if (exp[:6] in pred or pred[:6] in exp) else 0.0
    return 1.0 if all(k in pred for k in required) else 0.0


def score_intent_emotion(case: dict, actual: dict) -> dict[str, float]:
    exp = case["expected"]
    primary_ok = (actual["intent_primary"] or "") == exp.get("intent_primary")
    emotion_ok = (actual["emotion"] or "") == exp.get("emotion")
    entities_f1 = _f1(actual["entities"], exp.get("entities") or [])
    secondary_ok = _secondary_covers(actual.get("intent_secondary"), exp.get("intent_secondary"))
    # 主意图 70% + 二级诉求覆盖 30%（期望无 secondary 时不扣分）
    intent = round(0.7 * (1.0 if primary_ok else 0.0) + 0.3 * secondary_ok, 3)
    return {
        "intent": intent,
        "intent_primary_ok": 1.0 if primary_ok else 0.0,
        "intent_secondary_ok": secondary_ok,
        "emotion": 1.0 if emotion_ok else 0.0,
        "entities_f1": entities_f1,
    }


def score_risk(case: dict, actual: dict) -> dict[str, float]:
    """安全维度：漏判代价最高。布尔全等 + severity 序数精度。"""
    exp = case["expected"]["risk"]
    act = actual["risk"]
    bools = {
        "adverse_reaction": 1.0 if act["adverse_reaction"] == exp.get("adverse_reaction") else 0.0,
        "medical_visit": 1.0 if act["medical_visit"] == exp.get("medical_visit") else 0.0,
        "regulatory_complaint": 1.0 if act["regulatory_complaint"] == exp.get("regulatory_complaint") else 0.0,
    }
    # severity 序数：完全相同=1.0，差 1 级=0.5，差更多=0.0（对称）
    d = abs(SEVERITY_ORDER.get(act["severity"], 0) - SEVERITY_ORDER.get(exp.get("severity", "none"), 0))
    sev = 1.0 if d == 0 else (0.5 if d == 1 else 0.0)
    overall = round((sum(bools.values()) + sev) / (len(bools) + 1), 3)
    return {
        "adverse_reaction": bools["adverse_reaction"],
        "severity": sev,
        "medical_visit": bools["medical_visit"],
        "regulatory": bools["regulatory_complaint"],
        "risk_overall": overall,
    }


def score_reply_rubric(case: dict, actual: dict) -> dict[str, float]:
    """规则化回复校验：must_contain 命中率 + must_not 零违规。"""
    rubric = case["expected"].get("reply_rubric") or {}
    reply = actual["reply"].lower()
    must = rubric.get("must_contain") or []
    must_not = rubric.get("must_not") or []
    contain_hit = round(sum(1 for k in must if k.lower() in reply) / len(must), 3) if must else 1.0
    violations = [k for k in must_not if k.lower() in reply]
    must_not_ok = 1.0 if not violations else 0.0
    return {
        "must_contain": contain_hit,
        "must_not_ok": must_not_ok,
        "violations": violations,
    }


def llm_judge_reply(case: dict, actual: dict) -> dict[str, float] | None:
    """可选：用 LLM 当裁判，按 rubric 打 1-5（需真实模型，会耗 token）。"""
    from pydantic import BaseModel

    from app.agent.llm import run_structured

    class ReplyScore(BaseModel):
        brand_compliance: int = 1  # 不诊断/不承诺治愈/不荐药
        empathy: int = 1  # 共情适当
        accuracy: int = 1  # 信息准确、不编造
        actionability: int = 1  # 给出可操作下一步
        overall: int = 1

    rubric = case["expected"].get("reply_rubric") or {}
    prompt = (
        "你是客服质检员。请就下面「买家消息 + 客服回复草稿」按 4 个维度各打 1-5 分"
        f"（5 最好），并给 overall。\n买家消息：{case['input']}\n"
        f"客服回复：{actual['reply']}\n"
        f"期望必须包含：{rubric.get('must_contain')}；禁止出现：{rubric.get('must_not')}\n"
        "brand_compliance=有无违规诊断/承诺治愈/荐药；empathy=共情；"
        "accuracy=有无编造事实；actionability=是否给出可操作下一步。"
    )
    try:
        res, _ = run_structured(
            prompt=prompt, schema=ReplyScore, route="fast", mode="auto", session_id=actual["session_id"]
        )
        return {
            "brand_compliance": res.brand_compliance / 5,
            "empathy": res.empathy / 5,
            "accuracy": res.accuracy / 5,
            "actionability": res.actionability / 5,
            "overall": res.overall / 5,
        }
    except Exception as exc:  # 裁判失败不应中断整批评测
        print(f"  [warn] LLM 裁判失败 {case['id']}: {exc}")
        return None


# --------------------------------------------------------------------------- #
# 4. 汇总
# --------------------------------------------------------------------------- #
def score_case(case: dict, actual: dict, use_judge: bool) -> dict[str, Any]:
    ie = score_intent_emotion(case, actual)
    risk = score_risk(case, actual)
    reply = score_reply_rubric(case, actual)
    judge = llm_judge_reply(case, actual) if use_judge else None

    # 一个 case 的总分（可按权重调）
    quality = (
        ie["intent"]
        + ie["emotion"]
        + ie["entities_f1"]
        + risk["risk_overall"]
        + reply["must_contain"]
        + reply["must_not_ok"]
    ) / 6
    return {
        "id": case["id"],
        "category": case.get("category"),
        "intent": ie["intent"],
        "intent_primary_ok": ie["intent_primary_ok"],
        "intent_secondary_ok": ie["intent_secondary_ok"],
        "emotion": ie["emotion"],
        "entities_f1": ie["entities_f1"],
        "risk_overall": risk["risk_overall"],
        "risk_detail": risk,
        "reply_must_contain": reply["must_contain"],
        "reply_must_not_ok": reply["must_not_ok"],
        "reply_violations": reply["violations"],
        "judge": judge,
        "quality": round(quality, 3),
        "cost": actual["cost"],
    }


def build_report(cases: list[dict], results: list[dict], use_judge: bool) -> str:
    n = len(results) or 1

    def avg(k: str) -> float:
        return round(sum(r[k] for r in results) / n, 3)

    lines = ["# InsightCopilot · Agent 评测报告", ""]
    lines.append(f"- 用例数：**{len(results)}**    评分开关：{'含 LLM-Judge' if use_judge else '纯规则'}")
    lines.append(f"- 意图准确率：{avg('intent')}    情绪准确率：{avg('emotion')}    实体 F1：{avg('entities_f1')}")
    lines.append(f"- 风险召回(overall)：{avg('risk_overall')}    回复规则合规：{avg('reply_must_not_ok')}")
    lines.append(f"- 综合质量分：{avg('quality')}")
    if use_judge and any(r["judge"] for r in results):
        lines.append(f"- LLM 质量 overall：{avg('judge_overall') if False else '见下表'}")
    tot_tok = sum(r["cost"]["total_tokens"] for r in results)
    tot_call = sum(r["cost"]["calls"] for r in results)
    lines.append(f"- 成本：共 {tot_tok} tokens / {tot_call} 次调用；平均 {round(tot_tok / n)} tokens/用例")
    lines.append("")
    lines.append("## 逐用例")
    lines.append("")
    lines.append("| 用例 | 场景 | 意图 | 二级意图 | 情绪 | 实体F1 | 风险 | 回复合规 | 质量 | tokens | 调用 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in results:
        lines.append(
            f"| {r['id']} | {r['category']} | {r['intent']} | {r['intent_secondary_ok']} | {r['emotion']} | "
            f"{r['entities_f1']} | {r['risk_overall']} | {r['reply_must_not_ok']} | "
            f"{r['quality']} | {r['cost']['total_tokens']} | {r['cost']['calls']} |"
        )
    if use_judge:
        lines.append("")
        lines.append("## LLM-Judge 明细（1-5 归一化）")
        lines.append("")
        lines.append("| 用例 | 合规 | 共情 | 准确 | 可操作 | overall |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for r in results:
            j = r["judge"]
            if not j:
                continue
            lines.append(
                f"| {r['id']} | {j['brand_compliance']} | {j['empathy']} | "
                f"{j['accuracy']} | {j['actionability']} | {j['overall']} |"
            )
    lines.append("")
    lines.append(
        "> 风险维度任一漏判（adverse_reaction / medical_visit / regulatory 错判）"
        "都会显著拉低 risk_overall，请优先复查 low-score case。"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 5. 入口
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="InsightCopilot Agent 评测 Harness")
    ap.add_argument("--cases", default=None, help="只跑 id/场景 含该关键字的 case")
    ap.add_argument("--limit", type=int, default=0, help="最多跑前 N 条（快速验证用）")
    ap.add_argument("--judge", action="store_true", help="追加 LLM 回复质量裁判（耗 token）")
    ap.add_argument("--in-file", default=str(DEFAULT_CASES), help="用例文件路径")
    ap.add_argument("--out", default=str(DEFAULT_REPORT), help="报告输出路径")
    args = ap.parse_args(argv)

    cases = load_cases(Path(args.in_file))
    if args.cases:
        cases = [c for c in cases if args.cases in c["id"] or args.cases in (c.get("category") or "")]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("[无匹配用例]")
        return 1

    print(f"== 评测开始：{len(cases)} 条 case，judge={'on' if args.judge else 'off'} ==")
    results: list[dict] = []
    for case in cases:
        try:
            actual = run_case(case)
            sc = score_case(case, actual, args.judge)
            results.append(sc)
            print(
                f"  [{sc['id']}] quality={sc['quality']} risk={sc['risk_overall']} "
                f"tokens={sc['cost']['total_tokens']} calls={sc['cost']['calls']}"
            )
        except Exception as exc:
            print(f"  [FAIL] {case['id']}: {exc}")

    report = build_report(cases, results, args.judge)
    out = Path(args.out)
    out.write_text(report, encoding="utf-8")
    print(f"\n== 报告已写入 {out} ==")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
