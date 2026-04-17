from metiscode.session.message import (
    APIError,
    TextPart,
    ToolPart,
    UserMessage,
    from_error,
    parse_part,
)


def test_text_part_roundtrip() -> None:
    part = TextPart(content="hello")
    encoded = part.model_dump()
    decoded = TextPart.model_validate(encoded)
    assert decoded == part


def test_tool_part_state_transition() -> None:
    pending = ToolPart(tool_id="write", input={"path": "a.txt"}, state="pending")
    running = pending.model_copy(update={"state": "running"})
    completed = running.model_copy(update={"state": "completed", "output": "done"})
    assert pending.state == "pending"
    assert running.state == "running"
    assert completed.state == "completed"
    assert completed.output == "done"


def test_discriminated_union_parses_text_part() -> None:
    part = parse_part({"type": "text", "content": "hi"})
    assert isinstance(part, TextPart)
    assert part.content == "hi"


def test_user_message_accepts_optional_parts() -> None:
    message = UserMessage(id="msg_1")
    assert message.role == "user"
    assert message.parts == []
    assert isinstance(message.time_created, int)


def test_from_error_api_error_returns_text_part() -> None:
    part = from_error(APIError("boom", status_code=429))
    assert isinstance(part, TextPart)
    assert "APIError" in part.content
    assert "429" in part.content
    assert "boom" in part.content
