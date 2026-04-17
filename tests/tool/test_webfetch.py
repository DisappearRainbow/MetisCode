import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import metiscode.tool.webfetch as webfetch_module
from metiscode.tool import ToolContext, create_webfetch_tool

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


def test_webfetch_converts_html_to_text(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    webfetch_module._CACHE.clear()

    def fake_fetch_url(_url: str) -> tuple[str, str]:
        return "https://example.com/final", "<html><body><h1>Title</h1><p>Hello</p></body></html>"

    monkeypatch.setattr(webfetch_module, "_fetch_url", fake_fetch_url)

    tool = create_webfetch_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"url": "https://example.com/start"}, _context(asked)))

    assert "Title Hello" in result.output
    assert result.metadata["cached"] is False
    assert asked[0] == ("webfetch", ["https://example.com/start"])


def test_webfetch_uses_cache_on_second_call(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    webfetch_module._CACHE.clear()
    call_count = {"value": 0}

    def fake_fetch_url(_url: str) -> tuple[str, str]:
        call_count["value"] += 1
        return "https://example.com/final", "<html><body>Cached content</body></html>"

    monkeypatch.setattr(webfetch_module, "_fetch_url", fake_fetch_url)

    tool = create_webfetch_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    first = _run(instance.execute({"url": "https://example.com/a"}, _context(asked)))
    second = _run(instance.execute({"url": "https://example.com/a"}, _context(asked)))

    assert first.metadata["cached"] is False
    assert second.metadata["cached"] is True
    assert call_count["value"] == 1


def test_webfetch_returns_final_url_after_redirect(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    webfetch_module._CACHE.clear()

    def fake_fetch_url(_url: str) -> tuple[str, str]:
        return "https://example.com/redirected", "<html><body>Redirected</body></html>"

    monkeypatch.setattr(webfetch_module, "_fetch_url", fake_fetch_url)

    tool = create_webfetch_tool()
    instance = _run(tool.init("general"))
    asked: list[tuple[str, list[str]]] = []
    result = _run(instance.execute({"url": "https://example.com/source"}, _context(asked)))

    assert result.title == "https://example.com/redirected"
    assert result.metadata["final_url"] == "https://example.com/redirected"

