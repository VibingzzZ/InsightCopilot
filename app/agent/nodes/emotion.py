from langchain_core.output_parsers import PydanticOutputParser

from app.agent.schemas.analysis import EmotionAnalysis
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelGateway
from app.prompt.emotion import EMOTION_PROMPT

gateway = ModelGateway()

# deepseek-flash 是"思考模式"推理模型：不支持 json_schema 结构化输出，也不支持工具调用，
# 只支持 response_format={"type": "json_object"}，且要求 prompt 中必须包含 "json" 字样。
parser = PydanticOutputParser(pydantic_object=EmotionAnalysis)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser


def emotion_node(state: CustomerState) -> CustomerState:
    prompt = EMOTION_PROMPT.format(
        message=state["current_message"],
        format_instructions=parser.get_format_instructions(),
    )

    result = structured_llm.invoke(prompt)

    state["emotion"] = result.emotion

    return state


if __name__ == "__main__":
    state: CustomerState = {
        "conversation_id": "test-001",
        "current_message": "我的快递怎么还没到？",
        "intent": "",
        "emotion": "",
        "risk": {"adverse_reaction": False, "symptoms": [], "medical_visit": False},
        "risk_level": "",
        "order": {},
        "evidence": [],
        "reply_draft": "",
    }
    result = emotion_node(state)
    print("识别到的情绪：", result["emotion"])
