"""Prompt assembly and processor orchestration."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass

from metiscode.agent import AgentInfo
from metiscode.config.schema import ConfigInfo
from metiscode.project.models import ProjectInfo
from metiscode.session.message import ToolPart, parse_part
from metiscode.session.processor import ProcessResult, SessionProcessor, StreamInput
from metiscode.util.ids import ulid_str


def build_system_prompt(agent: AgentInfo, project: ProjectInfo, config: ConfigInfo) -> str:
    """Build merged system prompt text."""
    lines = [
        f"Agent: {agent.name}",
        f"Project worktree: {project.worktree}",
    ]
    if config.instructions:
        lines.append("Instructions:")
        lines.extend(config.instructions)
    if agent.prompt:
        lines.append("Agent prompt:")
        lines.append(agent.prompt)
    return "\n".join(lines)


def to_model_messages(
    messages: list[dict[str, object]],
    *,
    provider: str,
) -> list[dict[str, object]]:
    """Convert stored messages into provider-ready message list."""
    result: list[dict[str, object]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        parts_raw = message.get("parts", [])
        if not isinstance(parts_raw, list):
            parts_raw = []
        parts = [parse_part(part) for part in parts_raw if isinstance(part, dict)]

        if provider == "anthropic":
            content: list[dict[str, object]] = []
            for part in parts:
                if part.type == "text":
                    content.append({"type": "text", "text": part.content})
                elif part.type == "tool":
                    tool_part = ToolPart.model_validate(part.model_dump())
                    if tool_part.state == "completed":
                        content.append(
                            {
                                "type": "tool_use",
                                "id": tool_part.tool_id,
                                "name": tool_part.tool_id,
                                "input": tool_part.input,
                            }
                        )
            result.append({"role": role, "content": content})
            continue

        content_text = "\n".join(part.content for part in parts if part.type == "text")
        tool_calls = []
        for part in parts:
            if part.type != "tool":
                continue
            tool_part = ToolPart.model_validate(part.model_dump())
            if tool_part.state != "completed":
                continue
            tool_calls.append(
                {
                    "id": tool_part.tool_id,
                    "type": "function",
                    "function": {"name": tool_part.tool_id, "arguments": str(tool_part.input)},
                }
            )
        item: dict[str, object] = {"role": role, "content": content_text}
        if tool_calls:
            item["tool_calls"] = tool_calls
        result.append(item)
    return result


@dataclass(slots=True)
class SessionPrompt:
    """Glue layer between session storage and SessionProcessor."""

    processor_factory: Callable[[str, str], SessionProcessor]
    provider_resolver: Callable[[str], str]
    default_model: str = "anthropic:claude-sonnet-4-20250514"

    async def prompt(
        self,
        *,
        input_text: str,
        messages: list[dict[str, object]],
        session_id: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        resolved_session_id = session_id or ulid_str()
        message_id = ulid_str()
        selected_model = model or self.default_model
        provider = self.provider_resolver(selected_model)

        user_message = {
            "id": ulid_str(),
            "role": "user",
            "time_created": int(time.time() * 1000),
            "parts": [{"type": "text", "content": input_text}],
        }
        model_messages = to_model_messages([*messages, user_message], provider=provider)

        processor = self.processor_factory(resolved_session_id, message_id)
        stream_input = StreamInput(
            model=selected_model,
            messages=model_messages,
            tools=[],
            system="",
        )

        while True:
            result = await processor.process(stream_input)
            yield {"type": "processor_result", "value": result}
            if result == "stop":
                break
            if result == "compact":
                yield {"type": "compact_requested"}
                break
            if result == "continue":
                continue


def result_is_terminal(result: ProcessResult) -> bool:
    """Helper used in tests and orchestrators."""
    return result in {"stop", "compact"}
