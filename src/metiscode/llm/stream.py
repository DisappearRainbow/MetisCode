"""Unified streaming event model for LLM providers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from metiscode.provider import ProviderService

Streamer = Callable[
    [str, list[dict[str, object]], list[dict[str, object]], str],
    Awaitable[AsyncIterable[dict[str, object]]],
]


@dataclass(slots=True, frozen=True)
class TextStart:
    type: Literal["text_start"] = "text_start"


@dataclass(slots=True, frozen=True)
class TextDelta:
    content: str
    type: Literal["text_delta"] = "text_delta"


@dataclass(slots=True, frozen=True)
class ToolCallStart:
    tool_id: str
    name: str
    type: Literal["tool_call_start"] = "tool_call_start"


@dataclass(slots=True, frozen=True)
class ToolCallDelta:
    tool_id: str
    content: str
    type: Literal["tool_call_delta"] = "tool_call_delta"


@dataclass(slots=True, frozen=True)
class ToolCallEnd:
    tool_id: str
    name: str
    input_json: str
    type: Literal["tool_call_end"] = "tool_call_end"


@dataclass(slots=True, frozen=True)
class ToolResult:
    tool_id: str
    output: str
    type: Literal["tool_result"] = "tool_result"


@dataclass(slots=True, frozen=True)
class ReasoningStart:
    type: Literal["reasoning_start"] = "reasoning_start"


@dataclass(slots=True, frozen=True)
class ReasoningDelta:
    content: str
    type: Literal["reasoning_delta"] = "reasoning_delta"


@dataclass(slots=True, frozen=True)
class StepStart:
    type: Literal["step_start"] = "step_start"


@dataclass(slots=True, frozen=True)
class StepFinish:
    reason: str
    type: Literal["step_finish"] = "step_finish"


@dataclass(slots=True, frozen=True)
class ErrorEvent:
    message: str
    type: Literal["error"] = "error"


StreamEvent = (
    TextStart
    | TextDelta
    | ToolCallStart
    | ToolCallDelta
    | ToolCallEnd
    | ToolResult
    | ReasoningStart
    | ReasoningDelta
    | StepStart
    | StepFinish
    | ErrorEvent
)


class LLMService:
    """Normalize provider-specific chunks into StreamEvent taxonomy."""

    def __init__(
        self,
        *,
        provider_service: ProviderService | None = None,
        anthropic_streamer: Streamer | None = None,
        openai_streamer: Streamer | None = None,
        deepseek_streamer: Streamer | None = None,
    ) -> None:
        self._provider_service = provider_service or ProviderService()
        self._anthropic_streamer = anthropic_streamer
        self._openai_streamer = openai_streamer
        self._deepseek_streamer = deepseek_streamer

    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterator[StreamEvent]:
        model_ref = self._provider_service.parse_model(model)
        yield StepStart()
        try:
            if model_ref.provider_id == "anthropic":
                async for event in self._stream_anthropic(model, messages, tools, system):
                    yield event
            elif model_ref.provider_id == "deepseek":
                async for event in self._stream_deepseek(model, messages, tools, system):
                    yield event
            else:
                async for event in self._stream_openai(model, messages, tools, system):
                    yield event
            yield StepFinish(reason="stop")
        except Exception as error:  # noqa: BLE001
            yield ErrorEvent(message=str(error))
            yield StepFinish(reason="error")

    async def _stream_anthropic(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterator[StreamEvent]:
        if self._anthropic_streamer is None:
            raise RuntimeError("Anthropic streamer is not configured")
        raw_stream = await self._anthropic_streamer(model, messages, tools, system)
        tool_names: dict[str, str] = {}
        tool_args: dict[str, str] = {}
        for_text_started = False
        for_reasoning_started = False
        async for chunk in raw_stream:
            chunk_type = chunk.get("type")
            if chunk_type == "content_block_start":
                block = chunk.get("content_block")
                if isinstance(block, dict):
                    block_type = block.get("type")
                    if block_type == "text" and not for_text_started:
                        for_text_started = True
                        yield TextStart()
                    if block_type == "thinking" and not for_reasoning_started:
                        for_reasoning_started = True
                        yield ReasoningStart()
                    if block_type == "tool_use":
                        tool_id = str(block.get("id", "tool"))
                        name = str(block.get("name", "tool"))
                        tool_names[tool_id] = name
                        tool_args[tool_id] = ""
                        yield ToolCallStart(tool_id=tool_id, name=name)
            elif chunk_type == "content_block_delta":
                delta = chunk.get("delta")
                if isinstance(delta, dict):
                    delta_type = delta.get("type")
                    if delta_type == "text_delta":
                        text = delta.get("text")
                        if isinstance(text, str) and text:
                            if not for_text_started:
                                for_text_started = True
                                yield TextStart()
                            yield TextDelta(content=text)
                    elif delta_type == "thinking_delta":
                        thinking = delta.get("thinking")
                        if isinstance(thinking, str) and thinking:
                            if not for_reasoning_started:
                                for_reasoning_started = True
                                yield ReasoningStart()
                            yield ReasoningDelta(content=thinking)
                    elif delta_type == "input_json_delta":
                        partial = delta.get("partial_json")
                        block_id = chunk.get("id") or chunk.get("content_block_id")
                        if isinstance(partial, str) and isinstance(block_id, str):
                            tool_args[block_id] = tool_args.get(block_id, "") + partial
                            yield ToolCallDelta(tool_id=block_id, content=partial)
            elif chunk_type == "content_block_stop":
                block = chunk.get("content_block")
                block_id = chunk.get("id") or chunk.get("content_block_id")
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if isinstance(block_id, str):
                        name = tool_names.get(block_id, "tool")
                        args_text = tool_args.get(block_id, "")
                        yield ToolCallEnd(tool_id=block_id, name=name, input_json=args_text)

    async def _stream_openai(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterator[StreamEvent]:
        if self._openai_streamer is None:
            raise RuntimeError("OpenAI streamer is not configured")
        raw_stream = await self._openai_streamer(model, messages, tools, system)
        text_started = False
        reasoning_started = False
        tool_ids: dict[int, str] = {}
        tool_names: dict[int, str] = {}
        tool_args: dict[int, str] = {}
        async for chunk in raw_stream:
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            if not isinstance(first, dict):
                continue
            delta = first.get("delta")
            if not isinstance(delta, dict):
                continue

            content = delta.get("content")
            if isinstance(content, str) and content:
                if not text_started:
                    text_started = True
                    yield TextStart()
                yield TextDelta(content=content)

            reasoning = delta.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                if not reasoning_started:
                    reasoning_started = True
                    yield ReasoningStart()
                yield ReasoningDelta(content=reasoning)

            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, list):
                for item in tool_calls:
                    if not isinstance(item, dict):
                        continue
                    index = item.get("index")
                    function = item.get("function")
                    tool_id = item.get("id")
                    if not isinstance(index, int) or not isinstance(function, dict):
                        continue
                    if isinstance(tool_id, str):
                        tool_ids[index] = tool_id
                    call_id = tool_ids.get(index, f"tool_{index}")

                    name = function.get("name")
                    if isinstance(name, str):
                        tool_names[index] = name
                        if index not in tool_args:
                            tool_args[index] = ""
                            yield ToolCallStart(tool_id=call_id, name=name)

                    arguments = function.get("arguments")
                    if isinstance(arguments, str):
                        if index not in tool_args:
                            tool_args[index] = ""
                            yield ToolCallStart(tool_id=call_id, name=tool_names.get(index, "tool"))
                        tool_args[index] += arguments
                        yield ToolCallDelta(tool_id=call_id, content=arguments)

            finish_reason = first.get("finish_reason")
            if finish_reason == "tool_calls":
                for index, value in tool_args.items():
                    call_id = tool_ids.get(index, f"tool_{index}")
                    yield ToolCallEnd(
                        tool_id=call_id,
                        name=tool_names.get(index, "tool"),
                        input_json=value,
                    )

    async def _stream_deepseek(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterator[StreamEvent]:
        if self._deepseek_streamer is not None:
            raw_stream = await self._deepseek_streamer(model, messages, tools, system)
        elif self._openai_streamer is not None:
            raw_stream = await self._openai_streamer(model, messages, tools, system)
        else:
            raise RuntimeError("DeepSeek streamer is not configured")

        text_started = False
        reasoning_started = False
        tool_ids: dict[int, str] = {}
        tool_names: dict[int, str] = {}
        tool_args: dict[int, str] = {}
        async for chunk in raw_stream:
            choices = chunk.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            first = choices[0]
            if not isinstance(first, dict):
                continue
            delta = first.get("delta")
            if not isinstance(delta, dict):
                continue

            reasoning_content = delta.get("reasoning_content")
            if isinstance(reasoning_content, str) and reasoning_content:
                if not reasoning_started:
                    reasoning_started = True
                    yield ReasoningStart()
                yield ReasoningDelta(content=reasoning_content)

            content = delta.get("content")
            if isinstance(content, str) and content:
                if not text_started:
                    text_started = True
                    yield TextStart()
                yield TextDelta(content=content)

            tool_calls = delta.get("tool_calls")
            if isinstance(tool_calls, list):
                for item in tool_calls:
                    if not isinstance(item, dict):
                        continue
                    index = item.get("index")
                    function = item.get("function")
                    tool_id = item.get("id")
                    if not isinstance(index, int) or not isinstance(function, dict):
                        continue

                    if isinstance(tool_id, str):
                        tool_ids[index] = tool_id
                    call_id = tool_ids.get(index, f"tool_{index}")

                    name = function.get("name")
                    if isinstance(name, str):
                        tool_names[index] = name
                        if index not in tool_args:
                            tool_args[index] = ""
                            yield ToolCallStart(tool_id=call_id, name=name)

                    arguments = function.get("arguments")
                    if isinstance(arguments, str):
                        if index not in tool_args:
                            tool_args[index] = ""
                            yield ToolCallStart(tool_id=call_id, name=tool_names.get(index, "tool"))
                        tool_args[index] += arguments
                        yield ToolCallDelta(tool_id=call_id, content=arguments)

            finish_reason = first.get("finish_reason")
            if finish_reason == "tool_calls":
                for index, value in tool_args.items():
                    call_id = tool_ids.get(index, f"tool_{index}")
                    yield ToolCallEnd(
                        tool_id=call_id,
                        name=tool_names.get(index, "tool"),
                        input_json=value,
                    )


def merge_partial_json(parts: list[str]) -> dict[str, object]:
    """Merge chunked JSON argument pieces into one object."""
    text = "".join(parts)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if isinstance(value, dict):
        return value
    return {}
