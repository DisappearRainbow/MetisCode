import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import metiscode.tool.websearch as websearch_module
from metiscode.tool import ToolContext, create_websearch_tool

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


def test_websearch_formats_results(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_fetch_json(_query: str) -> dict[str, object]:
        return {
            "RelatedTopics": [
                {"Text": "Result One", "FirstURL": "https://example.com/1"},
                {"Text": "Result Two", "FirstURL": "https://example.com/2"},
            ]
        }

    monkeypatch.setattr(websearch_module, "_fetch_json", fake_fetch_json)

    tool = create_websearch_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"query": "test", "num_results": 2}, _context(asked)))

    assert "1. Result One" in result.output
    assert "URL: https://example.com/2" in result.output
    assert asked[0] == ("websearch", ["test"])


def test_websearch_returns_no_results_message(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_fetch_json(_query: str) -> dict[str, object]:
        return {"RelatedTopics": []}

    monkeypatch.setattr(websearch_module, "_fetch_json", fake_fetch_json)

    tool = create_websearch_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"query": "missing"}, _context(asked)))

    assert result.output == "No results found"
    assert result.metadata["count"] == 0

