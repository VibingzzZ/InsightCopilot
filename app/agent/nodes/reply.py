from langchain_core.output_parsers import PydanticOutputParser

from app.agent.schemas.analysis import ReplyDraft
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelGateway
from app.prompt.reply import REPLY_PROMPT

gateway = ModelGateway()

parser = PydanticOutputParser(pydantic_object=ReplyDraft)
structured_llm = gateway.get_ds_model().bind(response_format={"type": "json_object"}) | parser


def reply_node(state: CustomerState) -> dict:
    prompt = REPLY_PROMPT.format(
        intent=state["intent"],
        emotion=state["emotion"],
        evidence=state["evidence"],
        format_instructions=parser.get_format_instructions(),
    )

    result: ReplyDraft = structured_llm.invoke(prompt)

    return {"reply_draft": result.reply}