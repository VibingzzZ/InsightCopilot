import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import api_key

from app.integrations import model

load_dotenv()


# 模型调用网关：为后续模型经济调用做一个铺垫
class ModelGateway:
    def __init__(self):
        self.llm = ChatOpenAI(
            # 调用千问模型
            model=os.getenv("MODEL_FAST"),
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL"),
            temperature=0.5,
        )
        # 调用ds模型
        self.ds = ChatOpenAI(
            model=os.getenv("MODEL_DS"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
            temperature=0.5
        )
        if not model:
            raise ValueError("未设置模型，请检查.env文件配置")
        if not api_key:
            raise ValueError("未在环境变量中检测到 API_KEY，请检查 .env 文件配置")

    def get_fast_model(self):
        return self.llm

    def get_ds_model(self):
        return self.ds
