"""LLM 节点的结构化输出 Schema。

这些模型只描述「模型该产出什么」，对外的 I/O 契约在 contract.py。
坑：deepseek-flash 是思考模型，不支持 json_schema / tool calling，
只支持 response_format={"type": "json_object"}，且 prompt 里必须出现 "json" 字样。
"""

from pydantic import BaseModel, Field


class IntentAnalysis(BaseModel):
    intent_primary: str = Field(description="一级场景，如 订单服务 / 不良反应 / 物流问题 / 售前咨询")
    intent_secondary: str = Field(description="二级场景；无法判断时填 其他")
    entities: list[str] = Field(default_factory=list, description="订单号、商品名、金额、批次号、时间等实体")


class EmotionAnalysis(BaseModel):
    emotion: str = Field(description="当前主要情绪，如 平静 / 焦虑 / 不满 / 愤怒 / 急切")
    trend: str = Field(default="flat", description="情绪变化方向：up 上升 / flat 持平 / down 缓和")


class RiskExtraction(BaseModel):
    adverse_reaction: bool = Field(description="是否出现不良反应（红肿、刺痛、瘙痒、起疹、爆痘等）")
    severity: str = Field(
        default="none",
        description=(
            "不适程度，用于区分分级："
            "none 无不适 / mild 轻微泛红、刺痒或局部小颗粒且未加重 / "
            "obvious 范围扩大、持续加重、明显红肿 / severe 呼吸困难、眼部严重异常、住院"
        ),
    )
    symptoms: list[str] = Field(default_factory=list, description="症状关键词；无则空列表")
    medical_visit: bool = Field(description="是否明确表示已就医/已在医院")
    regulatory_complaint: bool = Field(description="是否提及监管投诉、平台投诉、曝光、律师或明确威胁")


class ReplyDraft(BaseModel):
    reply: str = Field(description="生成给客服编辑的回复文案")


class PromiseExtraction(BaseModel):
    has_promise: bool = Field(description="该消息中是否存在对消费者的明确承诺")
    promise_type: str = Field(default="other", description="refund / follow_up / replenishment / logistics / other")
    statement: str = Field(default="", description="标准化后的承诺内容")
    due_expression: str = Field(default="", description="时间的原始表达，如 '明天上午'、'3个工作日'；无则留空")
    owner_type: str = Field(default="agent", description="store / agent / team / system")
    confidence: float = Field(default=0.0, description="置信度 0 到 1")
