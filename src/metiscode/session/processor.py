"""Session processor main streaming loop."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Literal, Protocol

from metiscode.llm import (
    ErrorEvent,
    LLMService,
    ReasoningDelta,
    TextDelta,
    ToolCallDelta,
    ToolCallEnd,
    ToolCallStart,
)
from metiscode.tool import ToolContext, ToolRegistry
from metiscode.util.ids import ulid_str

ProcessResult = Literal["continue", "compact", "stop"]


class DBProtocol(Protocol):
    async def create_part(
        self,
        *,
        part_id: str,
        message_id: str,
        session_id: str,
        part_type: str,
        data: dict[str, object],
    ) -> None: ...


class BusProtocol(Protocol):
    async def publish(self, event: object, payload: object) -> None: ...


@dataclass(slots=True, frozen=True)
class StreamInput:
    """Processor input for one model step."""

    model: str
    messages: list[dict[str, object]]
    tools: list[dict[str, object]]
    system: str


@dataclass(slots=True)
class SessionProcessor:
    """State machine that consumes StreamEvents and updates persistence."""

    session_id: str
    message_id: str
    model: str
    agent: str
    abort: asyncio.Event
    llm: LLMService
    registry: ToolRegistry
    db: DBProtocol | None = None
    bus: BusProtocol | None = None
    _doom_loop_counter: dict[tuple[str, str], int] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        session_id: str,
        assistant_message_id: str,
        model: str,
        agent: str,
        abort: asyncio.Event,
        llm: LLMService,
        registry: ToolRegistry,
        db: DBProtocol | None = None,
        bus: BusProtocol | None = None,
    ) -> SessionProcessor:
        return cls(
            session_id=session_id,
            message_id=assistant_message_id,
            model=model,
            agent=agent,
            abort=abort,
            llm=llm,
            registry=registry,
            db=db,
            bus=bus,
        )

    async def process(self, stream_input: StreamInput) -> ProcessResult:
        text_content = ""
        reasoning_content = ""
        tool_used = False
        active_tools: dict[str, dict[str, object]] = {}

        async for event in self.llm.stream(
            model=stream_input.model,
            messages=stream_input.messages,
            tools=stream_input.tools,
            system=stream_input.system,
        ):
            if isinstance(event, TextDelta):
                text_content += event.content
            elif isinstance(event, ReasoningDelta):
                reasoning_content += event.content
            elif isinstance(event, ToolCallStart):
                active_tools[event.tool_id] = {"name": event.name, "input": ""}
            elif isinstance(event, ToolCallDelta):
                tool = active_tools.get(event.tool_id)
                if tool is not None:
                    tool["input"] = str(tool["input"]) + event.content
            elif isinstance(event, ToolCallEnd):
                tool_used = True
                await self._run_tool(event.tool_id, event.name, event.input_json)
            elif isinstance(event, ErrorEvent):
                if "ContextOverflow" in event.message:
                    return "compact"
                return "continue"

        if text_content:
            await self._create_part("text", {"type": "text", "content": text_content})
        if reasoning_content:
            await self._create_part(
                "reasoning",
                {"type": "reasoning", "content": reasoning_content},
            )

        await self._publish_message_completed()
        return "continue" if tool_used else "stop"

    async def _run_tool(self, tool_id: str, name: str, input_json: str) -> None:
        key = (name, input_json)
        self._doom_loop_counter[key] = self._doom_loop_counter.get(key, 0) + 1
        if self._doom_loop_counter[key] > 3:
            return

        info = self.registry.get(name)
        if info is None:
            await self._create_part(
                "tool",
                {
                    "type": "tool",
                    "tool_id": tool_id,
                    "input": {"raw": input_json},
                    "state": "error",
                    "error": f"Unknown tool: {name}",
                },
            )
            return

        instance = await info.init(self.agent)
        params = {}
        if input_json.strip():
            try:
                import json

                maybe = json.loads(input_json)
                if isinstance(maybe, dict):
                    params = maybe
            except Exception:  # noqa: BLE001
                params = {"raw": input_json}
        ctx = ToolContext(
            session_id=self.session_id,
            message_id=self.message_id,
            agent=self.agent,
            abort=self.abort,
            metadata=lambda _payload: None,
            ask=self._ask_passthrough,
            extra={"directory": ".", "worktree": ".", "db": self.db},
        )
        try:
            result = await instance.execute(params, ctx)
            await self._create_part(
                "tool",
                {
                    "type": "tool",
                    "tool_id": tool_id,
                    "input": params,
                    "state": "completed",
                    "output": result.output,
                    "metadata": result.metadata,
                },
            )
        except Exception as error:  # noqa: BLE001
            await self._create_part(
                "tool",
                {
                    "type": "tool",
                    "tool_id": tool_id,
                    "input": params,
                    "state": "error",
                    "error": str(error),
                },
            )

    async def _ask_passthrough(self, _permission: str, _patterns: list[str]) -> None:
        return None

    async def _create_part(self, part_type: str, data: dict[str, object]) -> None:
        if self.db is not None and hasattr(self.db, "create_part"):
            await self.db.create_part(
                part_id=ulid_str(),
                message_id=self.message_id,
                session_id=self.session_id,
                part_type=part_type,
                data=data,
            )
        if self.bus is not None and hasattr(self.bus, "publish"):
            await self.bus.publish(
                "part.created",
                {
                    "session_id": self.session_id,
                    "message_id": self.message_id,
                    "data": data,
                },
            )

    async def _publish_message_completed(self) -> None:
        if self.bus is not None and hasattr(self.bus, "publish"):
            await self.bus.publish(
                "message.completed",
                {"session_id": self.session_id, "message_id": self.message_id},
            )
