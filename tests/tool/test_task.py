import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from metiscode.tool import ToolContext, create_task_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


class _FakeDB:
    def __init__(self) -> None:
        self.created_sessions: list[dict[str, object]] = []

    async def create_session(self, **fields: object) -> None:
        self.created_sessions.append(fields)


def _context(
    asked: list[tuple[str, list[str]]],
    extra: dict[str, object] | None = None,
) -> ToolContext:
    async def ask(permission: str, patterns: list[str]) -> None:
        asked.append((permission, patterns))

    def metadata(_payload: dict[str, object]) -> None:
        return None

    return ToolContext(
        session_id="sess_parent",
        message_id="msg_1",
        agent="general",
        abort=asyncio.Event(),
        metadata=metadata,
        ask=ask,
        extra=extra,
    )


def test_task_creates_subsession_and_returns_task_result() -> None:
    async def runner(params, _ctx):  # type: ignore[no-untyped-def]
        return f"done: {params.prompt}"

    db = _FakeDB()
    tool = create_task_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"description": "short task", "prompt": "analyze", "subagent_type": "explore"},
            _context(asked, extra={"db": db, "directory": "C:/proj", "task_runner": runner}),
        )
    )

    assert db.created_sessions
    assert db.created_sessions[0]["parent_id"] == "sess_parent"
    assert asked[0] == ("task", ["explore"])
    assert "<task_result>" in result.output


def test_task_uses_existing_task_id_when_provided() -> None:
    db = _FakeDB()
    tool = create_task_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {
                "description": "resume",
                "prompt": "continue",
                "subagent_type": "general",
                "task_id": "task_existing",
            },
            _context(asked, extra={"db": db, "directory": "C:/proj"}),
        )
    )

    assert db.created_sessions == []
    assert "task_id: task_existing" in result.output


def test_task_defaults_subagent_type_to_general() -> None:
    tool = create_task_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    _ = _run(
        instance.execute(
            {"description": "default", "prompt": "run"},
            _context(asked),
        )
    )

    assert asked[0] == ("task", ["general"])
