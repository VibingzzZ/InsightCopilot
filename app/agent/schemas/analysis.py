from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    intent: str = Field(description="用户当前咨询的业务意图")
    reason: str = Field(description="解释原因")


class EmotionAnalysis(BaseModel):
    emotion: str = Field(description="用户当前信息表现出的情绪")

class RiskExtraction(BaseModel):
    adverse_reaction: bool = Field(description="用户是否出现不良反应（红肿、疼痛、起疹等）")
    symptoms: list[str] = Field(description="症状关键词列表，如 ['脸红','疼痛']；无则空列表")
    medical_visit: bool = Field(description="用户是否明确表示已就医/去医院")