import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv()

api_key = os.getenv("DASHSCOPE_API_KEY")

llm = ChatOpenAI(
    model=os.getenv("MODEL_FAST", ""),
    api_key=SecretStr(api_key) if api_key else None,
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
)
