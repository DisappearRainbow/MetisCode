import asyncio

from metiscode.agent import AgentInfo
from metiscode.config.schema import ConfigInfo
from metiscode.project.models import ProjectInfo, ProjectTime
from metiscode.session.prompt import (
    SessionPrompt,
    build_system_prompt,
    result_is_terminal,
    to_model_messages,
)


def _project() -> ProjectInfo:
    return ProjectInfo(
        id="p1",
        worktree="C:/repo",
        vcs="git",
        sandboxes=[],
        time=ProjectTime(created=1, updated=1),
    )


def test_build_system_prompt_includes_agent_and_instructions() -> None:
    agent = AgentInfo(
        name="build",
        mode="primary",
        permission=[],
        prompt="Do build tasks",
    )
    config = ConfigInfo(instructions=["One", "Two"])
    prompt = build_system_prompt(agent, _project(), config)
    assert "Agent: build" in prompt
    assert "One" in prompt
    assert "Do build tasks" in prompt


def test_to_model_messages_maps_text_part_for_anthropic() -> None:
    messages = [{"role": "user", "parts": [{"type": "text", "content": "hello"}]}]
    converted = to_model_messages(messages, provider="anthropic")
    assert converted[0]["role"] == "user"
    assert converted[0]["content"] == [{"type": "text", "text": "hello"}]


def test_to_model_messages_maps_completed_tool_part_for_openai() -> None:
    messages = [
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool",
                    "tool_id": "write",
                    "input": {"path": "a.py"},
                    "state": "completed",
                    "output": "ok",
                    "error": None,
                    "metadata": None,
                }
            ],
        }
    ]
    converted = to_model_messages(messages, provider="openai")
    assert "tool_calls" in converted[0]
    assert converted[1]["role"] == "tool"
    assert converted[1]["tool_call_id"] == "write"


def test_session_prompt_loops_until_stop() -> None:
    class _FakeProcessor:
        def __init__(self) -> None:
            self.calls = 0

        async def process(self, _stream_input):  # type: ignore[no-untyped-def]
            self.calls += 1
            return "continue" if self.calls == 1 else "stop"

    fake_processor = _FakeProcessor()

    def processor_factory(_session_id: str, _message_id: str):  # type: ignore[no-untyped-def]
        return fake_processor

    session_prompt = SessionPrompt(
        processor_factory=processor_factory,
        provider_resolver=lambda _model: "openai",
    )

    async def collect() -> list[dict[str, object]]:
        events = []
        async for event in session_prompt.prompt(
            input_text="hello",
            messages=[],
            session_id="sess_1",
            model="openai:gpt-4.1",
        ):
            events.append(event)
        return events

    events = asyncio.run(collect())
    assert len(events) == 2
    assert events[-1]["value"] == "stop"


def test_result_is_terminal_for_stop_and_compact() -> None:
    assert result_is_terminal("stop") is True
    assert result_is_terminal("compact") is True
    assert result_is_terminal("continue") is False
