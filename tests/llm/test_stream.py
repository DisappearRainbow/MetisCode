import asyncio

from metiscode.llm import LLMService, merge_partial_json


async def _collect(service: LLMService, model: str) -> list[object]:
    events: list[object] = []
    async for event in service.stream(model=model, messages=[], tools=[], system="sys"):
        events.append(event)
    return events


def test_anthropic_stream_normalizes_text_and_reasoning() -> None:
    async def anthropic_streamer(_model, _messages, _tools, _system):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            yield {"type": "content_block_start", "content_block": {"type": "text"}}
            yield {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hello"}}
            yield {"type": "content_block_start", "content_block": {"type": "thinking"}}
            yield {
                "type": "content_block_delta",
                "delta": {"type": "thinking_delta", "thinking": "hmm"},
            }

        return gen()

    service = LLMService(anthropic_streamer=anthropic_streamer)
    events = asyncio.run(_collect(service, "anthropic:claude-sonnet-4-20250514"))
    event_types = [event.type for event in events]  # type: ignore[attr-defined]
    assert event_types[:6] == [
        "step_start",
        "text_start",
        "text_delta",
        "reasoning_start",
        "reasoning_delta",
        "step_finish",
    ]


def test_openai_stream_normalizes_tool_call_fragments() -> None:
    async def openai_streamer(_model, _messages, _tools, _system):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "write", "arguments": '{"a":'},
                                },
                            ]
                        }
                    }
                ]
            }
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": '"b"}'}},
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }

        return gen()

    service = LLMService(openai_streamer=openai_streamer)
    events = asyncio.run(_collect(service, "openai:gpt-4.1"))
    event_types = [event.type for event in events]  # type: ignore[attr-defined]
    assert "tool_call_start" in event_types
    assert "tool_call_delta" in event_types
    assert "tool_call_end" in event_types


def test_deepseek_maps_reasoning_content_to_reasoning_delta() -> None:
    async def deepseek_streamer(_model, _messages, _tools, _system):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            yield {"choices": [{"delta": {"reasoning_content": "thinking", "content": "answer"}}]}

        return gen()

    service = LLMService(deepseek_streamer=deepseek_streamer)
    events = asyncio.run(_collect(service, "deepseek:deepseek-reasoner"))
    event_types = [event.type for event in events]  # type: ignore[attr-defined]
    assert "reasoning_delta" in event_types
    assert "text_delta" in event_types


def test_deepseek_normalizes_tool_call_fragments() -> None:
    async def deepseek_streamer(_model, _messages, _tools, _system):  # type: ignore[no-untyped-def]
        async def gen():  # type: ignore[no-untyped-def]
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {
                                        "name": "write",
                                        "arguments": '{"file_path":"a.py"',
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
            yield {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": ',"content":"print(1)"}'}},
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }

        return gen()

    service = LLMService(deepseek_streamer=deepseek_streamer)
    events = asyncio.run(_collect(service, "deepseek:deepseek-chat"))
    event_types = [event.type for event in events]  # type: ignore[attr-defined]
    assert "tool_call_start" in event_types
    assert "tool_call_delta" in event_types
    assert "tool_call_end" in event_types


def test_merge_partial_json_handles_fragmented_arguments() -> None:
    merged = merge_partial_json(['{"x":', '1,', '"y":"z"}'])
    assert merged == {"x": 1, "y": "z"}


def test_stream_emits_error_event_on_provider_failure() -> None:
    async def failing_openai_streamer(_model, _messages, _tools, _system):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    service = LLMService(openai_streamer=failing_openai_streamer)
    events = asyncio.run(_collect(service, "openai:gpt-4.1"))
    event_types = [event.type for event in events]  # type: ignore[attr-defined]
    assert "error" in event_types
