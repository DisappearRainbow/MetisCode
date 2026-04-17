"""HTTP-backed provider streamers for LLMService."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterable, AsyncIterator
from urllib import error as urlerror
from urllib import request as urlrequest

from metiscode.provider.service import ProviderService


def _stringify_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        segments: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    segments.append(text)
        return "".join(segments)
    return ""


def _debug_dump_response(
    provider_id: str,
    payload: dict[str, object],
    response: dict[str, object],
) -> None:
    if os.getenv("METISCODE_DEBUG_PROVIDER_JSON", "").lower() not in {"1", "true", "yes"}:
        return
    payload_text = json.dumps(payload, ensure_ascii=False)[:3000]
    response_text = json.dumps(response, ensure_ascii=False)[:3000]
    sys.stderr.write(f"[provider-debug] provider={provider_id} payload={payload_text}\n")
    sys.stderr.write(f"[provider-debug] provider={provider_id} response={response_text}\n")


class HTTPStreamers:
    """Provider HTTP adapters that emit pseudo-stream chunks."""

    def __init__(self, provider_service: ProviderService | None = None) -> None:
        self._provider_service = provider_service or ProviderService()

    async def openai_streamer(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterable[dict[str, object]]:
        return await self._openai_compatible_streamer(
            model=model,
            messages=messages,
            tools=tools,
            system=system,
            default_base_url="https://api.openai.com/v1",
        )

    async def deepseek_streamer(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterable[dict[str, object]]:
        return await self._openai_compatible_streamer(
            model=model,
            messages=messages,
            tools=tools,
            system=system,
            default_base_url="https://api.deepseek.com/v1",
        )

    async def _openai_compatible_streamer(
        self,
        *,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
        default_base_url: str,
    ) -> AsyncIterable[dict[str, object]]:
        model_ref = self._provider_service.parse_model(model)
        options = self._provider_service.resolve_options(model_ref)
        api_key = options.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            provider = self._provider_service.provider(model_ref.provider_id)
            raise RuntimeError(f"Missing API key env: {provider.api_key_env}")

        base_url = options.get("base_url")
        if not isinstance(base_url, str) or not base_url:
            base_url = default_base_url
        url = f"{base_url.rstrip('/')}/chat/completions"

        request_messages = list(messages)
        if system.strip():
            request_messages = [{"role": "system", "content": system}, *request_messages]

        payload: dict[str, object] = {
            "model": model_ref.model_id,
            "messages": request_messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        response = await self._post_json(
            url=url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        _debug_dump_response(model_ref.provider_id, payload, response)

        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI-compatible response missing choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeError("OpenAI-compatible response choice is invalid")

        message = first.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("OpenAI-compatible response missing message")

        chunks: list[dict[str, object]] = []
        text = _stringify_content(message.get("content"))
        if text:
            chunks.append({"choices": [{"delta": {"content": text}, "finish_reason": None}]})

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            delta_tool_calls: list[dict[str, object]] = []
            for index, call in enumerate(tool_calls):
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                arguments = function.get("arguments")
                if not isinstance(name, str):
                    continue
                if not isinstance(arguments, str):
                    arguments = json.dumps(arguments if arguments is not None else {})
                item: dict[str, object] = {
                    "index": index,
                    "id": call.get("id") if isinstance(call.get("id"), str) else f"tool_{index}",
                    "function": {"name": name, "arguments": arguments},
                }
                delta_tool_calls.append(item)
            if delta_tool_calls:
                chunks.append(
                    {
                        "choices": [
                            {
                                "delta": {"tool_calls": delta_tool_calls},
                                "finish_reason": None,
                            }
                        ]
                    }
                )
                chunks.append({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})
            else:
                chunks.append({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        else:
            finish_reason = first.get("finish_reason")
            if not isinstance(finish_reason, str):
                finish_reason = "stop"
            chunks.append({"choices": [{"delta": {}, "finish_reason": finish_reason}]})

        return _chunk_stream(chunks)

    async def anthropic_streamer(
        self,
        model: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        system: str,
    ) -> AsyncIterable[dict[str, object]]:
        model_ref = self._provider_service.parse_model(model)
        options = self._provider_service.resolve_options(model_ref)
        api_key = options.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            provider = self._provider_service.provider(model_ref.provider_id)
            raise RuntimeError(f"Missing API key env: {provider.api_key_env}")

        base_url = options.get("base_url")
        if not isinstance(base_url, str) or not base_url:
            base_url = "https://api.anthropic.com/v1"
        url = f"{base_url.rstrip('/')}/messages"

        payload: dict[str, object] = {
            "model": model_ref.model_id,
            "max_tokens": 4096,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
        if system.strip():
            payload["system"] = system

        response = await self._post_json(
            url=url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            payload=payload,
        )
        _debug_dump_response(model_ref.provider_id, payload, response)

        content_blocks = response.get("content")
        if not isinstance(content_blocks, list):
            raise RuntimeError("Anthropic response missing content list")

        chunks: list[dict[str, object]] = []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                block_id = "text_0"
                chunks.append(
                    {
                        "type": "content_block_start",
                        "id": block_id,
                        "content_block": {"type": "text"},
                    }
                )
                text = block.get("text")
                if isinstance(text, str) and text:
                    chunks.append(
                        {
                            "type": "content_block_delta",
                            "id": block_id,
                            "content_block_id": block_id,
                            "delta": {"type": "text_delta", "text": text},
                        }
                    )
                continue
            if block_type == "thinking":
                block_id = "thinking_0"
                chunks.append(
                    {
                        "type": "content_block_start",
                        "id": block_id,
                        "content_block": {"type": "thinking"},
                    }
                )
                thinking = block.get("thinking")
                if isinstance(thinking, str) and thinking:
                    chunks.append(
                        {
                            "type": "content_block_delta",
                            "id": block_id,
                            "content_block_id": block_id,
                            "delta": {"type": "thinking_delta", "thinking": thinking},
                        }
                    )
                continue
            if block_type == "tool_use":
                tool_id = block.get("id") if isinstance(block.get("id"), str) else "tool_0"
                tool_name = block.get("name") if isinstance(block.get("name"), str) else "tool"
                chunks.append(
                    {
                        "type": "content_block_start",
                        "id": tool_id,
                        "content_block_id": tool_id,
                        "content_block": {
                            "type": "tool_use",
                            "id": tool_id,
                            "name": tool_name,
                        },
                    }
                )
                input_payload = block.get("input")
                json_text = json.dumps(input_payload if input_payload is not None else {})
                chunks.append(
                    {
                        "type": "content_block_delta",
                        "id": tool_id,
                        "content_block_id": tool_id,
                        "delta": {"type": "input_json_delta", "partial_json": json_text},
                    }
                )
                chunks.append(
                    {
                        "type": "content_block_stop",
                        "id": tool_id,
                        "content_block_id": tool_id,
                        "content_block": {"type": "tool_use"},
                    }
                )

        return _chunk_stream(chunks)

    async def _post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")

        def _request() -> dict[str, object]:
            req = urlrequest.Request(url=url, data=body, headers=headers, method="POST")
            try:
                with urlrequest.urlopen(req, timeout=120) as response:
                    raw = response.read().decode("utf-8")
            except urlerror.HTTPError as error:
                detail = error.read().decode("utf-8", errors="ignore")
                raise RuntimeError(f"HTTP {error.code}: {detail}") from error
            except urlerror.URLError as error:
                raise RuntimeError(f"Network error: {error.reason}") from error

            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as error:
                raise RuntimeError("Invalid JSON response from provider") from error
            if not isinstance(parsed, dict):
                raise RuntimeError("Provider response must be a JSON object")
            return parsed

        return await asyncio.to_thread(_request)


async def _chunk_stream(chunks: list[dict[str, object]]) -> AsyncIterator[dict[str, object]]:
    for chunk in chunks:
        yield chunk
