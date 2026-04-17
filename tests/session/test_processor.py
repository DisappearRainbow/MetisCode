import asyncio
from collections.abc import AsyncIterator

from pydantic import BaseModel, ConfigDict

from metiscode.llm import ErrorEvent, TextDelta, ToolCallDelta, ToolCallEnd, ToolCallStart
from metiscode.session.processor import SessionProcessor, StreamInput
from metiscode.tool import ToolContext, ToolRegistry, ToolResult, define


class _FakeLLM:
    def __init__(self, events: list[object]) -> None:
        self.events = events

    async def stream(  # type: ignore[no-untyped-def]
        self,
        *,
        model,
        messages,
        tools,
        system,
    ) -> AsyncIterator[object]:
        _ = (model, messages, tools, system)
        for event in self.events:
            yield event


class _FakeDB:
    def __init__(self) -> None:
        self.parts: list[dict[str, object]] = []

    async def create_part(  # type: ignore[no-untyped-def]
        self,
        *,
        part_id,
        message_id,
        session_id,
        part_type,
        data,
    ) -> None:
        self.parts.append(
            {
                "part_id": part_id,
                "message_id": message_id,
                "session_id": session_id,
                "part_type": part_type,
                "data": data,
            }
        )


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[object, object]] = []

    async def publish(self, event: object, payload: object) -> None:
        self.events.append((event, payload))


class _EchoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


def _registry_with_echo_tool() -> ToolRegistry:
    async def execute(params: _EchoParams, _ctx: ToolContext) -> ToolResult:
        return ToolResult(title="echo", output=params.text, metadata={})

    registry = ToolRegistry()
    registry.register(define("echo", "echo", _EchoParams, execute))
    return registry


def test_processor_persists_text_delta_as_text_part() -> None:
    llm = _FakeLLM([TextDelta(content="hello")])
    db = _FakeDB()
    bus = _FakeBus()
    processor = SessionProcessor.create(
        session_id="sess_1",
        assistant_message_id="msg_1",
        model="openai:gpt-4.1",
        agent="general",
        abort=asyncio.Event(),
        llm=llm,  # type: ignore[arg-type]
        registry=ToolRegistry(),
        db=db,
        bus=bus,
    )

    result = asyncio.run(
        processor.process(StreamInput(model="openai:gpt-4.1", messages=[], tools=[], system="sys"))
    )
    assert result == "stop"
    assert db.parts and db.parts[0]["part_type"] == "text"
    assert db.parts[0]["data"]["content"] == "hello"  # type: ignore[index]


def test_processor_executes_tool_call_and_marks_completed() -> None:
    llm = _FakeLLM(
        [
            ToolCallStart(tool_id="t1", name="echo"),
            ToolCallDelta(tool_id="t1", content='{"text":"ok"}'),
            ToolCallEnd(tool_id="t1", name="echo", input_json='{"text":"ok"}'),
        ]
    )
    db = _FakeDB()
    processor = SessionProcessor.create(
        session_id="sess_1",
        assistant_message_id="msg_1",
        model="openai:gpt-4.1",
        agent="general",
        abort=asyncio.Event(),
        llm=llm,  # type: ignore[arg-type]
        registry=_registry_with_echo_tool(),
        db=db,
        bus=_FakeBus(),
    )

    result = asyncio.run(
        processor.process(StreamInput(model="openai:gpt-4.1", messages=[], tools=[], system="sys"))
    )
    assert result == "continue"
    tool_parts = [part for part in db.parts if part["part_type"] == "tool"]
    assert tool_parts
    assert tool_parts[0]["data"]["state"] == "completed"  # type: ignore[index]


def test_processor_error_returns_continue_for_retryable_error() -> None:
    processor = SessionProcessor.create(
        session_id="sess_1",
        assistant_message_id="msg_1",
        model="openai:gpt-4.1",
        agent="general",
        abort=asyncio.Event(),
        llm=_FakeLLM([ErrorEvent(message="temporary network error")]),  # type: ignore[arg-type]
        registry=ToolRegistry(),
        db=_FakeDB(),
        bus=_FakeBus(),
    )
    result = asyncio.run(
        processor.process(StreamInput(model="openai:gpt-4.1", messages=[], tools=[], system="sys"))
    )
    assert result == "continue"


def test_processor_error_returns_compact_for_context_overflow() -> None:
    processor = SessionProcessor.create(
        session_id="sess_1",
        assistant_message_id="msg_1",
        model="openai:gpt-4.1",
        agent="general",
        abort=asyncio.Event(),
        llm=_FakeLLM([ErrorEvent(message="ContextOverflow: context window exceeded")]),  # type: ignore[arg-type]
        registry=ToolRegistry(),
        db=_FakeDB(),
        bus=_FakeBus(),
    )
    result = asyncio.run(
        processor.process(StreamInput(model="openai:gpt-4.1", messages=[], tools=[], system="sys"))
    )
    assert result == "compact"

