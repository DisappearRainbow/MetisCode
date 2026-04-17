"""Message and part type definitions for session pipeline."""

from __future__ import annotations

import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from metiscode.util.errors import MetiscodeError


class APIError(MetiscodeError):
    """Represents upstream LLM API failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class TextPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["text"] = "text"
    content: str


class ReasoningPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["reasoning"] = "reasoning"
    content: str


ToolState = Literal["pending", "running", "completed", "error"]


class ToolPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["tool"] = "tool"
    tool_id: str
    input: dict[str, object]
    state: ToolState
    output: str | None = None
    error: str | None = None
    metadata: dict[str, object] | None = None


class StepStartPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["step_start"] = "step_start"
    step: int


class StepFinishPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["step_finish"] = "step_finish"
    step: int
    reason: str


class CompactionPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["compaction"] = "compaction"
    summary: str


class FilePart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["file"] = "file"
    path: str
    operation: str


class SubtaskPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["subtask"] = "subtask"
    session_id: str
    description: str


Part = Annotated[
    TextPart
    | ReasoningPart
    | ToolPart
    | StepStartPart
    | StepFinishPart
    | CompactionPart
    | FilePart
    | SubtaskPart,
    Field(discriminator="type"),
]


class UserMessage(BaseModel):
    """User message with discriminated parts."""

    model_config = ConfigDict(extra="forbid")
    id: str
    role: Literal["user"] = "user"
    parts: list[Part] = Field(default_factory=list)
    time_created: int = Field(default_factory=lambda: int(time.time() * 1000))


class AssistantMessage(BaseModel):
    """Assistant message with model provenance."""

    model_config = ConfigDict(extra="forbid")
    id: str
    role: Literal["assistant"] = "assistant"
    parts: list[Part] = Field(default_factory=list)
    model: str
    time_created: int = Field(default_factory=lambda: int(time.time() * 1000))
    time_completed: int | None = None


def parse_part(data: dict[str, object]) -> Part:
    """Parse raw dict into discriminated part instance."""
    part_type = data.get("type")
    if part_type == "text":
        return TextPart.model_validate(data)
    if part_type == "reasoning":
        return ReasoningPart.model_validate(data)
    if part_type == "tool":
        return ToolPart.model_validate(data)
    if part_type == "step_start":
        return StepStartPart.model_validate(data)
    if part_type == "step_finish":
        return StepFinishPart.model_validate(data)
    if part_type == "compaction":
        return CompactionPart.model_validate(data)
    if part_type == "file":
        return FilePart.model_validate(data)
    if part_type == "subtask":
        return SubtaskPart.model_validate(data)
    raise ValueError(f"Unknown part type: {part_type!r}")


def from_error(error: Exception) -> TextPart:
    """Map runtime exceptions to a user-visible text part."""
    if isinstance(error, APIError):
        status_segment = f" (status={error.status_code})" if error.status_code is not None else ""
        return TextPart(content=f"APIError{status_segment}: {error}")
    return TextPart(content=f"{type(error).__name__}: {error}")

