import asyncio

import pytest

from metiscode.provider import HTTPStreamers, ProviderService


def test_openai_streamer_emits_text_and_tool_call_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProviderService()
    streamers = HTTPStreamers(service)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    async def fake_post_json(**_kwargs):  # type: ignore[no-untyped-def]
        return {
            "choices": [
                {
                    "message": {
                        "content": "hello",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "write", "arguments": '{"file_path":"a.py"}'},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    monkeypatch.setattr(streamers, "_post_json", fake_post_json)

    async def collect() -> list[dict[str, object]]:
        stream = await streamers.openai_streamer("openai:gpt-4.1", [], [], "")
        items: list[dict[str, object]] = []
        async for item in stream:
            items.append(item)
        return items

    chunks = asyncio.run(collect())
    assert chunks[0]["choices"][0]["delta"]["content"] == "hello"  # type: ignore[index]
    assert "tool_calls" in chunks[1]["choices"][0]["delta"]  # type: ignore[index]
    assert chunks[2]["choices"][0]["finish_reason"] == "tool_calls"  # type: ignore[index]


def test_openai_streamer_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProviderService()
    streamers = HTTPStreamers(service)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    async def collect() -> None:
        await streamers.openai_streamer("openai:gpt-4.1", [], [], "")

    with pytest.raises(RuntimeError, match="Missing API key"):
        asyncio.run(collect())


def test_anthropic_streamer_emits_tool_use_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ProviderService()
    streamers = HTTPStreamers(service)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    async def fake_post_json(**_kwargs):  # type: ignore[no-untyped-def]
        return {
            "content": [
                {"type": "text", "text": "ready"},
                {
                    "type": "tool_use",
                    "id": "tool_1",
                    "name": "write",
                    "input": {"file_path": "a.py"},
                },
            ]
        }

    monkeypatch.setattr(streamers, "_post_json", fake_post_json)

    async def collect() -> list[dict[str, object]]:
        stream = await streamers.anthropic_streamer(
            "anthropic:claude-sonnet-4-20250514",
            [],
            [],
            "",
        )
        items: list[dict[str, object]] = []
        async for item in stream:
            items.append(item)
        return items

    chunks = asyncio.run(collect())
    assert any(chunk.get("type") == "content_block_delta" for chunk in chunks)
    assert any(chunk.get("type") == "content_block_stop" for chunk in chunks)
