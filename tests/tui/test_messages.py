from metiscode.tui.messages import MessageList, render_assistant_tool_part, render_user_message


def test_add_user_message_renders_content() -> None:
    messages = MessageList()
    messages.add_message({"role": "user", "content": "hello"})
    rendered = render_user_message("hello")
    assert "hello" in rendered
    assert messages.entries


def test_add_completed_tool_part_renders_tool_name() -> None:
    text = render_assistant_tool_part("write", "completed")
    assert "write" in text
    assert "completed" in text

