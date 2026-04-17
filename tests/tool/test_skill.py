import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from metiscode.tool import ToolContext, create_skill_tool

T = TypeVar("T")


def _run(coro: Awaitable[T]) -> T:  # noqa: UP047
    return asyncio.run(coro)


def _context(
    asked: list[tuple[str, list[str]]],
    extra: dict[str, object] | None = None,
) -> ToolContext:
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
        extra=extra,
    )


def test_skill_loads_existing_skill() -> None:
    tool = create_skill_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(
        instance.execute(
            {"skill_name": "python"},
            _context(asked, extra={"skills": {"python": "do x"}}),
        )
    )

    assert result.title == "Loaded skill: python"
    assert result.output == "do x"
    assert asked[0] == ("skill", ["python"])


def test_skill_raises_not_found() -> None:
    tool = create_skill_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    try:
        _ = _run(instance.execute({"skill_name": "missing"}, _context(asked, extra={"skills": {}})))
    except ValueError as error:
        assert "skill not found" in str(error)
    else:
        raise AssertionError("Expected ValueError for missing skill")
