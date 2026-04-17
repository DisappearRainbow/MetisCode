import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from metiscode.tool import ToolContext, create_plan_exit_tool, create_question_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _context(asked: list[tuple[str, list[str]]]) -> ToolContext:
    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(_payload: dict[str, object]) -> None:
        return None

    return ToolContext(
        session_id="sess_1",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
    )


def test_question_tool_calls_ctx_ask() -> None:
    tool = create_question_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"question": "Continue?", "options": ["Yes", "No"]},
            _context(asked),
        )
    )

    assert asked[0] == ("question", ["Yes", "No"])
    assert "Continue?" in result.output


def test_plan_exit_tool_returns_plan_exit_flag() -> None:
    tool = create_plan_exit_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({}, _context(asked)))

    assert result.metadata["plan_exit"] is True
    assert "Switching to build agent" in result.title

