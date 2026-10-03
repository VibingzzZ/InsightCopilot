"""图片识别节点（AG-10）。

只在消息里存在图片时生效：
- 有真实图片数据（image_url / image_b64 / image_path）且模型可用 → 调 Vision
- 有图片但无数据、或模型不可用 → Mock 占位（明确「待识别」，交人工确认）
- 无图片 → 直接返回 {}，不产生任何调用

"""

import base64
import time

from langchain_core.messages import HumanMessage

from app.agent import cost
from app.agent.llm import format_instructions
from app.agent.mock import mock_vision
from app.agent.schemas.analysis import VisionExtraction
from app.agent.schemas.contract import EvidenceRef
from app.agent.state import CustomerState
from app.integrations.model.gateway import ModelUnavailableError, gateway
from app.prompt.vision import VISION_PROMPT


def _collect_images(state: CustomerState) -> list[dict]:
    return [m for m in (state.get("messages") or []) if m.get("content_type") == "image"]


def _image_part(message: dict) -> dict | None:
    """把消息里的图片数据转成 langchain 多模态 content 片段。"""
    if message.get("image_url"):
        return {"type": "image_url", "image_url": {"url": message["image_url"]}}
    if message.get("image_b64"):
        mime = message.get("image_mime") or "image/png"
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{message['image_b64']}"}}
    if message.get("image_path"):
        try:
            with open(message["image_path"], "rb") as fh:
                b64 = base64.b64encode(fh.read()).decode()
            return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        except OSError:
            return None
    return None


def _run_vision(images: list[dict], prompt: str, mode: str) -> tuple[VisionExtraction, bool]:
    model = gateway.model_name_for("vision")
    parts = [part for part in (_image_part(m) for m in images) if part]

    if mode == "mock" or not parts:
        cost.record_call(route="vision", model=model, mode=mode, latency_ms=0, degraded=True)
        return mock_vision(images), True

    if not gateway.is_available("vision"):
        if mode == "real":
            raise ModelUnavailableError("mode=real 但 vision 路由未配置模型，无法执行")
        cost.record_call(route="vision", model=model, mode=mode, latency_ms=0, error="route unavailable", degraded=True)
        return mock_vision(images), True

    token_capture = cost.TokenCapture()
    started = time.monotonic()
    try:
        llm = gateway.get("vision").bind(response_format={"type": "json_object"})
        message = HumanMessage(content=[{"type": "text", "text": prompt}, *parts])
        response = llm.invoke([message], config={"callbacks": [token_capture]})
        content = response.content if isinstance(response.content, str) else str(response.content)
        result = VisionExtraction.model_validate_json(content)
        latency_ms = int((time.monotonic() - started) * 1000)
        cost.record_call(
            route="vision",
            model=model,
            mode=mode,
            latency_ms=latency_ms,
            input_tokens=token_capture.input_tokens,
            output_tokens=token_capture.output_tokens,
            total_tokens=token_capture.total_tokens,
        )
        return result, False
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        if mode == "real":
            raise
        cost.record_call(route="vision", model=model, mode=mode, latency_ms=latency_ms, error=str(exc), degraded=True)
        return mock_vision(images), True


def vision_node(state: CustomerState) -> dict:
    images = _collect_images(state)
    if not images:
        return {}

    prompt = VISION_PROMPT.format(format_instructions=format_instructions(VisionExtraction))
    result, degraded = _run_vision(images, prompt, state.get("mode", "auto"))

    first = images[0]
    quote = f"图片识别：{result.clarity} / {result.image_type}" if result.clarity != "待识别" else "图片待人工确认"
    evidence = EvidenceRef(
        source_type="image",
        source_id=str(first.get("message_id") or "image"),
        message_id=first.get("message_id"),
        quote=quote,
    )

    return {"vision": result.model_dump(), "evidence": [evidence], "degraded": degraded}
