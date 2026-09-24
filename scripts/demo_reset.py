# Demo演示一键重置逻辑

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import ActionExecution, AIAnalysis, AuditLog, Promise


def reset_demo_state():
    """3秒内完成演示环境重置"""
    db = SessionLocal()
    try:
        # 开启事务清理演示过程中产生的动态数据
        db.query(ActionExecution).delete()
        db.query(Promise).delete()
        db.query(AIAnalysis).delete()

        # 写入一条审计记录
        audit = AuditLog(
            request_id="reset_req_001",
            operator_id="system_admin",
            entity_type="system",
            entity_id="demo_db",
            operation="demo_reset",
            before_json="{}",
            after_json='{"status": "reset_completed"}',
        )
        db.add(audit)

        db.commit()
        print("【Demo 重置成功】已清空本次演示产生的临时操作与承诺，数据恢复为初始基线状态！")
    except Exception as e:
        db.rollback()
        print(f"重置失败, 事务已整笔回滚: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    reset_demo_state()
