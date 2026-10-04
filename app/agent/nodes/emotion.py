from app.agent.llm import format_instructions, run_structured
from app.agent.mock import mock_emotion
from app.agent.schemas.analysis import EmotionAnalysis
from app.agent.state import CustomerState
from app.prompt.emotion import EMOTION_PROMPT


def emotion_node(state: CustomerState) -> dict:
    prompt = EMOTION_PROMPT.format(
        message=state["current_message"],
        format_instructions=format_instructions(EmotionAnalysis),
    )

    result, degraded = run_structured(
        prompt=prompt,
        schema=EmotionAnalysis,
        route="fast",
        mode=state.get("mode", "auto"),
        fallback=lambda: mock_emotion(state["current_message"]),
    )

    return {
        "emotion": result.emotion,
        "emotion_trend": result.trend,
        "degraded": degraded,
    }
