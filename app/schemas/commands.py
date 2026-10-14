# app/schemas/commands.py — 替换为如下（只需修改两处：导入 StrEnum + raise ... from exc）
"""结构化功能指令的契约与解析校验（Task 01）。"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

# adjust_tone 支持的语气风格
ToneType = Literal["polite", "empathetic", "concise", "warm"]


class CommandType(StrEnum):
    """支持的功能指令。新增指令只需在此枚举 + rewrite.py 注册目标即可。"""

    ADJUST_TONE = "adjust_tone"
    OPTIMIZE_EXPRESSION = "optimize_expression"


# 需要携带 draft 的改写类指令；新增指令若也吃草稿，在此登记即可。
REWRITE_COMMANDS = {CommandType.ADJUST_TONE, CommandType.OPTIMIZE_EXPRESSION}


class FunctionCommand(BaseModel):
    """前端发来的结构化功能指令。

    - command: 指令名（必须在 CommandType 内）
    - params:  指令参数（容错：缺省给空字典，多余字段忽略）
    - draft:   待处理的当前草稿（改写类指令必填）
    """

    command: CommandType
    params: dict[str, Any] = Field(default_factory=dict)
    draft: str = ""


class CommandError(Exception):
    """指令解析失败。携带 code 供前端定位，message 供前端展示。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def parse_command(raw: Any) -> FunctionCommand:
    """从任意输入解析指令；失败抛 CommandError。"""
    if not isinstance(raw, dict):
        raise CommandError("BAD_FORMAT", "指令必须是 JSON 对象")
    if "command" not in raw:
        raise CommandError("MISSING_COMMAND", "缺少 command 字段")

    try:
        cmd = FunctionCommand(**raw)
    except ValidationError as exc:
        reason = exc.errors()[0].get("msg", str(exc))
        # 显式链出原来的 ValidationError（修复 Ruff B904）
        raise CommandError("INVALID_COMMAND", f"指令校验失败：{reason}") from exc

    if cmd.command in REWRITE_COMMANDS and not cmd.draft.strip():
        raise CommandError("EMPTY_DRAFT", "改写类指令需要提供 draft 草稿内容")

    return cmd