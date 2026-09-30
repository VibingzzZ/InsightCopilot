# Demo 演示一键重置：恢复 baseline-v1 固定初始数据（退款/不良反应/赠品补发）
#
# 用法（在项目根目录执行）：
#   py scripts/demo_reset.py                 # 恢复全部场景，保留 Excel 导入数据
#   py scripts/demo_reset.py --no-preserve   # 同时清理 Excel 导入数据
#   py scripts/demo_reset.py --scenario all  # 与 Demo 接口 POST /api/demo/reset 行为一致

import argparse
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.db import reset_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复 Demo 基线数据")
    parser.add_argument(
        "--scenario",
        default="all",
        choices=["all", "refund", "adverse_reaction", "gift_resend"],
        help="演示场景（默认 all）",
    )
    parser.add_argument(
        "--no-preserve",
        action="store_true",
        help="同时清理 Excel 导入数据（默认保留）",
    )
    args = parser.parse_args()

    db = SessionLocal()
    started = time.perf_counter()
    try:
        result = reset_demo(
            db,
            scenario=args.scenario,
            preserve_import=not args.no_preserve,
        )
        db.commit()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        counts = result["counts"]
        print("【Demo 重置成功】已恢复 baseline-v1 初始状态")
        print(f"  场景: {args.scenario} | 耗时: {elapsed_ms}ms")
        print(
            "  数据量: "
            f"消费者 {counts['consumers']} / 会话 {counts['sessions']} / 消息 {counts['messages']} / "
            f"订单 {counts['orders']} / 工单 {counts['tickets']} / 承诺 {counts['promises']} / 事件 {counts['events']}"
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - 脚本层兜底，事务整笔回滚
        db.rollback()
        print(f"重置失败，事务已整笔回滚: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
