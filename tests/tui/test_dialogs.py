from metiscode.tui.dialogs import PermissionDialog


def test_permission_dialog_displays_tool_and_pattern() -> None:
    dialog = PermissionDialog(request_id="r1", tool_name="bash", pattern="git *")
    text = dialog.display_text()
    assert "bash" in text
    assert "git *" in text


def test_permission_dialog_allow_once_returns_expected_reply() -> None:
    dialog = PermissionDialog(request_id="r2", tool_name="read", pattern="*")
    request_id, action = dialog.resolve("once")
    assert request_id == "r2"
    assert action == "once"

