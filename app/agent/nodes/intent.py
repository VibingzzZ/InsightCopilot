from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_intent
from app.agent.schemas.analysis import IntentAnalysis
from app.agent.state import CustomerState
from app.prompt.intent_prompt import INTENT_PROMPT


def intent_node(state: CustomerState) -> dict:
    prompt = INTENT_PROMPT.format(
        message=state["current_message"],
        format_instructions=format_instructions(IntentAnalysis),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=IntentAnalysis,
        route="fast",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_intent(state["current_message"]),
    )

    return {
        "intent": {
            "primary": result.intent_primary,
            "secondary": result.intent_secondary,
            "entities": result.entities,
        },
        "degraded": degraded,
    }
