# 模拟数据导入与脱敏工具

import hashlib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.models import (
    Consumer,
    ServiceEvent,
    ServiceSession,
    utc_now,
)


def hash_nickname(nickname: str) -> str:
    """对原始昵称求哈希，原始值不写库"""
    return hashlib.sha256(nickname.encode("utf-8")).hexdigest()


def mask_display_name(name: str) -> str:
    """脱敏展示名称，如：魏h**"""
    if not name:
        return "用户**"
    return name[0] + "**"


def seed_baseline_data():
    db = SessionLocal()
    try:
        # 1. 创建测试消费者
        c1 = Consumer(
            consumer_id="C00015",
            display_name_masked=mask_display_name("魏海波"),
            nickname_hash=hash_nickname("魏海波_raw_nick"),
            risk_level="L0",
        )
        db.merge(c1)

        # 2. 创建测试会话 S00015
        s1 = ServiceSession(
            session_id="S00015",
            consumer_id="C00015",
            store_name="官方旗舰店",
            scene_major="售后",
            scene_minor="补发",
            status="open",
            last_message_at=utc_now().isoformat(),
        )
        db.merge(s1)

        # merge 到 flush 之前不会真正落库，先落库再插事件，否则外键约束会失败
        db.flush()

        # 3. 创建时间线事件
        evt = ServiceEvent(
            consumer_id="C00015",
            session_id="S00015",
            event_type="message",
            occurred_at=utc_now().isoformat(),
            actor_type="buyer",
            title="会话初始化",
            content="消费者进入会话 S00015",
        )
        db.add(evt)

        db.commit()
        print("模拟初始化基线数据成功！")
    except Exception as e:
        db.rollback()
        print(f"数据插入失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_baseline_data()
