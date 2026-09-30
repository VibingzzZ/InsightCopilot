# 官方 Excel 数据导入与脱敏工具
#
# 用法（在项目根目录执行）：
#   py scripts/import_excel.py --inspect                  # 查看工作表与列名（校准映射用）
#   py scripts/import_excel.py                            # 导入默认路径数据文件
#   py scripts/import_excel.py "data/你的文件.xlsx"        # 导入指定文件
#
# 导入默认保留基线数据（baseline-v1），重复运行按业务主键幂等 upsert。

import argparse
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal  # noqa: E402
from app.db.excel_import import import_workbook, inspect_workbook  # noqa: E402

DEFAULT_EXCEL_PATH = Path("data/赛题 1：数据共情者-业务数据.xlsx")


def main() -> int:
    parser = argparse.ArgumentParser(description="导入官方 Excel 数据")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(DEFAULT_EXCEL_PATH),
        help=f"Excel 文件路径（默认 {DEFAULT_EXCEL_PATH}）",
    )
    parser.add_argument("--inspect", action="store_true", help="仅打印工作表与列名，不写库")
    args = parser.parse_args()

    excel_path = Path(args.path)
    if not excel_path.is_file():
        print(f"未找到 Excel 文件: {excel_path}")
        print("请将官方数据文件放入 data/ 目录，或通过参数指定路径；")
        print("如需先体验 Demo，可执行: py scripts/demo_reset.py 生成基线数据。")
        return 1

    if args.inspect:
        inspect_workbook(excel_path)
        return 0

    db = SessionLocal()
    try:
        stats = import_workbook(excel_path, db)
        db.commit()
        print("【导入完成】")
        print(
            "  会话 {sessions} / 消息 {messages} / 订单 {orders} / 工单 {tickets} / 消费者 {consumers} / 事件 {events}".format(
                **stats.as_dict()
            )
        )
        if stats.skipped_rows:
            print(f"  跳过行数: {stats.skipped_rows}")
        if stats.unlinked_rows:
            print(f"  未关联行数: {stats.unlinked_rows}")
        for warning in stats.warnings:
            print(f"  [警告] {warning}")
        return 0
    except Exception as exc:  # noqa: BLE001 - 脚本层兜底，事务整笔回滚
        db.rollback()
        print(f"导入失败，事务已整笔回滚: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
