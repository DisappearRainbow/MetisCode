import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from metiscode.tool import ToolContext, ToolResult, define

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


class EchoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def _context(metadata_events: list[dict[str, object]]) -> ToolContext:
    async def ask(_permission: str, _patterns: list[str]) -> None:
        return None

    def metadata(payload: dict[str, object]) -> None:
        metadata_events.append(payload)

    return ToolContext(
        session_id="sess_1",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
    )


def test_define_echo_tool_execute_returns_output() -> None:
    async def execute(params: EchoParams, _ctx: ToolContext) -> ToolResult:
        return ToolResult(title="echo", output=params.text, metadata={})

    tool = define("echo", "Echo text", EchoParams, execute)
    instance = _run(tool.init("general"))
    result = _run(instance.execute({"text": "hello"}, _context([])))

    assert result.title == "echo"
    assert result.output == "hello"
    assert result.metadata["truncated"] is False


def test_invalid_params_raise_validation_error() -> None:
    async def execute(params: EchoParams, _ctx: ToolContext) -> ToolResult:
        return ToolResult(title="echo", output=params.text, metadata={})

    tool = define("echo", "Echo text", EchoParams, execute)
    instance = _run(tool.init("general"))

    with pytest.raises(ValidationError):
        _run(instance.execute({"bad": "arg"}, _context([])))


def test_long_output_is_truncated() -> None:
    async def execute(_params: EchoParams, _ctx: ToolContext) -> ToolResult:
        return ToolResult(title="echo", output="x" * 200, metadata={})

    tool = define("echo", "Echo text", EchoParams, execute, max_output_chars=50)
    instance = _run(tool.init("general"))
    result = _run(instance.execute({"text": "ignored"}, _context([])))

    assert result.metadata["truncated"] is True
    assert "...output truncated..." in result.output
    assert len(result.output) > 50


def test_context_metadata_callback_is_recorded() -> None:
    async def execute(_params: EchoParams, ctx: ToolContext) -> ToolResult:
        ctx.metadata({"key": "val"})
        return ToolResult(title="ok", output="done", metadata={"hello": "world"})

    events: list[dict[str, object]] = []
    tool = define("meta", "Metadata emitter", EchoParams, execute)
    instance = _run(tool.init("general"))
    _ = _run(instance.execute({"text": "ignored"}, _context(events)))

    assert events == [{"key": "val"}]

