"""Agent 离线评测脚本（EVA-01 / EVA-02）。

用法：
  python scripts/eval_agent.py                       # 全量评测，mode=auto（无 Key 自动降级 Mock）
  python scripts/eval_agent.py --mock                # 强制 Mock，结果可复现
  python scripts/eval_agent.py --test-ratio 0.33 --seed 42   # 会话级切分，只在测试集上出指标

EVA-01 会话级切分：split_by_session 保证同一会话只落在 train 或 test 一侧，避免泄漏。
EVA-02 指标：意图一级/二级、情绪、风险等级用准确率；承诺抽取用 Precision / Recall / F1。
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.run import extract_promises, run_copilot
from app.agent.schemas.contract import AgentMode, CopilotRequest, PromiseExtractRequest

DEFAULT_ANNOTATIONS = Path(__file__).resolve().parents[1] / "data" / "annotations.json"


def load_annotations(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def flatten(annotations: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for session_id, session in annotations["sessions"].items():
        for msg in session["messages"]:
            samples.append({"session_id": session_id, **msg})
    return samples


def split_by_session(
    samples: list[dict[str, Any]], test_ratio: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """会话级切分：同一会话不会同时出现在 train 和 test 里，避免数据泄漏。"""
    session_ids = sorted({s["session_id"] for s in samples})
    rng = random.Random(seed)
    rng.shuffle(session_ids)
    n_test = max(1, int(len(session_ids) * test_ratio)) if test_ratio > 0 else 0
    test_sessions = set(session_ids[:n_test])
    train = [s for s in samples if s["session_id"] not in test_sessions]
    test = [s for s in samples if s["session_id"] in test_sessions]
    return train, test


def predict_copilot(sample: dict[str, Any], mode: AgentMode) -> dict[str, Any]:
    request = CopilotRequest(session_id=sample["session_id"], current_message=sample["message_text"], mode=mode)
    result = run_copilot(request)
    return {
        "intent_primary": result.insight.intent_primary,
        "intent_secondary": result.insight.intent_secondary,
        "emotion": result.insight.emotion,
        "risk_level": result.insight.risk_level,
    }


def accuracy(preds: list[Any], golds: list[Any]) -> float:
    if not golds:
        return 0.0
    return sum(1 for p, g in zip(preds, golds, strict=False) if p == g) / len(golds)


def binary_metrics(preds: list[bool], golds: list[bool]) -> dict[str, float]:
    tp = sum(1 for p, g in zip(preds, golds, strict=False) if p and g)
    fp = sum(1 for p, g in zip(preds, golds, strict=False) if p and not g)
    fn = sum(1 for p, g in zip(preds, golds, strict=False) if not p and g)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def evaluate_copilot(samples: list[dict[str, Any]], mode: AgentMode) -> dict[str, Any]:
    preds = [predict_copilot(s, mode) for s in samples]
    golds = [s["expected"] for s in samples]
    return {
        "intent_primary_acc": accuracy([p["intent_primary"] for p in preds], [g["intent_primary"] for g in golds]),
        "intent_secondary_acc": accuracy(
            [p["intent_secondary"] for p in preds], [g["intent_secondary"] for g in golds]
        ),
        "emotion_acc": accuracy([p["emotion"] for p in preds], [g["emotion"] for g in golds]),
        "risk_level_acc": accuracy([p["risk_level"] for p in preds], [g["risk_level"] for g in golds]),
        "n": len(samples),
    }


def evaluate_promises(annotations: dict[str, Any], mode: AgentMode) -> dict[str, Any]:
    preds_has: list[bool] = []
    golds_has: list[bool] = []
    preds_type: list[str] = []
    golds_type: list[str] = []

    for item in annotations.get("promises", []):
        result = extract_promises(
            PromiseExtractRequest(session_id="eval", message_id="m", message_text=item["message_text"], mode=mode)
        )
        cand = result.candidate
        pred_has = cand is not None and cand.promise_type != "other"
        preds_has.append(pred_has)
        golds_has.append(bool(item["expected"].get("has_promise")))
        preds_type.append(cand.promise_type if cand else "other")
        golds_type.append(item["expected"].get("promise_type", "other"))

    has_metrics = binary_metrics(preds_has, golds_has)
    return {
        "has_promise_precision": has_metrics["precision"],
        "has_promise_recall": has_metrics["recall"],
        "has_promise_f1": has_metrics["f1"],
        "promise_type_acc": accuracy(preds_type, golds_type),
        "n": len(golds_has),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent 离线评测")
    parser.add_argument("--mock", action="store_true", help="强制 Mock，结果可复现")
    parser.add_argument("--test-ratio", type=float, default=0.0, help="测试集比例（>0 时按会话切分）")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--annotations", default=str(DEFAULT_ANNOTATIONS))
    args = parser.parse_args(argv)

    mode: AgentMode = "mock" if args.mock else "auto"
    annotations = load_annotations(Path(args.annotations))
    samples = flatten(annotations)

    target = split_by_session(samples, args.test_ratio, args.seed)[1] if args.test_ratio > 0 else samples

    print(f"== Agent 评测（mode={mode}, n={len(target)}）==")
    print(json.dumps(evaluate_copilot(target, mode), ensure_ascii=False, indent=2))
    print("== 承诺抽取 ==")
    print(json.dumps(evaluate_promises(annotations, mode), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
