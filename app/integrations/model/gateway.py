import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()


# 模型调用网关：为后续模型经济调用做一个铺垫
class ModelGateway:
    def __init__(self):
        self.llm = ChatOpenAI(
            # 调用千问模型
            model=os.getenv("MODEL_FAST"),
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=os.getenv("DASHSCOPE_BASE_URL"),
        )
        # 调用ds模型
        self.ds = ChatOpenAI(
            model=os.getenv("MODEL_DS"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL"),
        )

    def get_fast_model(self):
        return self.llm

    def get_ds_model(self):
        return self.ds
