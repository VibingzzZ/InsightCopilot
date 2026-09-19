from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    intent: str = Field(description="用户当前咨询的业务意图")
