from langchain_core.output_parsers import PydanticOutputParser

from app.agent.schemas.analysis import RiskExtraction
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelGateway
from app.prompt.risk import RISK_EXTRACTION_PROMPT

gateway = ModelGateway()

# 和 intent/emotion 完全一致的模式：
# deepseek-flash 只支持 response_format={"type": "json_object"}，prompt 里必须有 "json" 字样
parser = PydanticOutputParser(pydantic_object=RiskExtraction)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser


def risk_extraction_node(state: CustomerState) -> dict:
    prompt = RISK_EXTRACTION_PROMPT.format(
        message=state["current_message"],
        format_instructions=parser.get_format_instructions(),
    )

    result: RiskExtraction = structured_llm.invoke(prompt)

    # Pydantic 对象 → dict，塞进 state["risk"]
    return {"risk": result.model_dump()}
