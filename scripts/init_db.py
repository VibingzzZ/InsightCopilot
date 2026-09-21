import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from app.models import Base


def init_database():
    print("正在创建数据库与 10 张核心表...")
    Base.metadata.create_all(bind=engine)
    print("建表成功！")

if __name__ == "__main__":
    init_database()