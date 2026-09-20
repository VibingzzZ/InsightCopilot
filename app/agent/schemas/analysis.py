from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    intent: str = Field(description="用户当前咨询的业务意图")
    reason: str = Field(description="解释原因")

class EmotionAnalysis(BaseModel):
    emotion: str =Field(
        description="用户当前信息表现出的护腰情绪"
    )
